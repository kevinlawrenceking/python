import sys, argparse, pyodbc, os, time, traceback, zipfile, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from scraper_base import log_message, setup_logging, get_db_cursor, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"


def extract_doc_rows(soup):
    return [tr for tr in soup.find_all("tr") if tr.find("a", href=re.compile("doc1")) and 'document_' in str(tr)]

def parse_doc_row(tr, base_url, pdf_type, default_pdf_title):
    tds = tr.find_all("td")
    try:
        a_tag = tr.find("a", href=re.compile(r'doc1'))
        if not a_tag:
            return None

        pdf_url = a_tag['href']
        if not pdf_url.startswith("http"):
            pdf_url = base_url + pdf_url

        match = re.search(r'/doc1/(\d+)', pdf_url)
        doc_id = int(match.group(1)) if match else None

        pdf_no = int(a_tag.text.strip()) if a_tag.text.strip().isdigit() else 0
        desc = default_pdf_title if pdf_type == "Docket" else " ".join(td.get_text(strip=True) for td in tds[2:4])

        return {
            "doc_id": doc_id,
            "pdf_url": pdf_url,
            "pdf_title": desc,
            "pdf_type": pdf_type,
            "pdf_no": pdf_no,
            "rel_path": "pending"
        }
    except:
        return None

def main():
    parser = argparse.ArgumentParser(description="Download PACER PDF for specific case_event")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    try:
        conn, cursor = get_db_cursor()
        # Ensure arr_de_seq_nums is populated
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET arr_de_seq_nums = 
                SUBSTRING(
                    event_url,
                    CHARINDEX('de_seq_num=', event_url) + 11,
                    CHARINDEX('&', event_url + '&', CHARINDEX('de_seq_num=', event_url)) 
                    - CHARINDEX('de_seq_num=', event_url) - 11
                )
            WHERE event_url IS NOT NULL
            AND arr_de_seq_nums IS NULL
            AND event_url LIKE '%de_seq_num%'
        """)
        conn.commit()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        log_message(cursor, fk_task_run, "INFO", f"Processing case_event_id: {args.case_event_id}")

        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in DB.")
            return
        USERNAME, PASSWORD, LOGIN_URL = row

        cursor.execute("""
            SELECT c.id AS case_id,
                c.pacer_id, 
                LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
                e.event_description, e.event_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE e.id = ?
        """, (args.case_event_id,))
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "INFO", f"No event found for ID {args.case_event_id}")
            return

        case_id, pacer_id, base_url, event_description, event_url = row

        # Setup headless Chrome
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        prefs = {
            "download.default_directory": FINAL_PDF_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1
        }
        opts.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        wait = WebDriverWait(driver, 15)

        # Login
        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.NAME, "loginForm:loginName"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
        try:
            driver.find_element(By.NAME, "loginForm:clientCode").send_keys("DocketWatch")
        except:
            pass
        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        time.sleep(3)

        # Load the event page
        driver.get(event_url)
        time.sleep(2)

        if "referrer_form" in driver.page_source:
            try:
                driver.find_element(By.ID, "referrer_form").submit()
                time.sleep(3)
                log_message(cursor, fk_task_run, "INFO", "PACER CSRF form submitted.")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Referrer form submission failed: {str(e)}")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        doc_rows = extract_doc_rows(soup)
        inserted = 0

        if not doc_rows:
            match = re.search(r'/doc1/(\d+)', event_url)
            if match:
                doc_id = int(match.group(1))
                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_id,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'pending', GETDATE())
                    """, (
                        case_id, args.case_event_id, 2, doc_id, event_url, event_description
                    ))
                    conn.commit()
                    log_message(cursor, fk_task_run, "INFO", f"Inserted fallback docket PDF {doc_id}")
        else:
            for i, tr in enumerate(doc_rows):
                pdf_type = "Docket" if i == 0 else "Attachment"
                doc_data = parse_doc_row(tr, base_url, pdf_type, event_description)
                if not doc_data or not doc_data["doc_id"]:
                    continue
                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_data["doc_id"],))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
                    """, (
                        case_id, args.case_event_id, 2,
                        doc_data["doc_id"], doc_data["pdf_url"],
                        doc_data["pdf_title"], doc_data["pdf_type"],
                        doc_data["pdf_no"], doc_data["rel_path"]
                    ))
                    inserted += 1
            conn.commit()
            log_message(cursor, fk_task_run, "INFO", f"Inserted metadata for {inserted} documents.")

        # Now query for those documents with rel_path = 'pending' and download the actual PDFs
        cursor.execute("""
         
 SELECT 
        c.pacer_id AS case_id,
                       c.id AS fk_case,
        LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
        e.event_description,
        e.event_url,
        e.arr_de_seq_nums,
        p.doc_uid,
        ps.url,
        p.doc_id,
        RIGHT(CAST(p.doc_id AS VARCHAR), 8) AS doc_id_str,
        p.pdf_type,
        ps.url + '/cgi-bin/show_multidocs.pl?caseid=' + 
        CAST(c.pacer_id AS VARCHAR) +
        '&arr_de_seq_nums=' + 
        CAST(e.arr_de_seq_nums AS VARCHAR) +
        '&pdf_header=2&pdf_toggle_possible=1' +
        CASE 
            WHEN EXISTS (
                SELECT 1 
                FROM docketwatch.dbo.documents p2 
                WHERE p2.fk_case_event = e.id 
                AND p2.doc_id <> p.doc_id
            )
            THEN '&exclude_attachments=' + ISNULL((
                STUFF((
                    SELECT ',' + RIGHT(CAST(p2.doc_id AS VARCHAR), 8)
                    FROM docketwatch.dbo.documents p2
                    WHERE p2.fk_case_event = e.id 
                    AND p2.doc_id <> p.doc_id
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 1, '')
            ), '')
            ELSE ''
        END +
        '&zipit=1' AS download_url

        FROM docketwatch.dbo.case_events e
        INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
        INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
        INNER JOIN docketwatch.dbo.documents p ON p.fk_case_event = e.id
		        WHERE e.id = ? 
        """, (args.case_event_id,))
        rows = cursor.fetchall()

        for row in rows:
            doc_id = row.doc_id
            doc_uid = row.doc_uid
            fk_case = row.fk_case
            download_url = row.download_url
            filename = f"E{doc_id}.pdf"
            case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
            os.makedirs(case_dir, exist_ok=True)
            dest_path = os.path.join(case_dir, filename)

            try:
                log_message(cursor, fk_task_run, "INFO", f"Download URL for doc_id {doc_id}: {download_url}")
                driver.get(download_url)
                time.sleep(8)

                if "Warning:" in driver.page_source and "referrer_form" in driver.page_source:
                    try:
                        form = driver.find_element(By.ID, "referrer_form")
                        driver.execute_script("arguments[0].submit();", form)
                        time.sleep(3)
                        log_message(cursor, fk_task_run, "INFO", "Submitted CSRF referrer form.")
                    except Exception as e:
                        log_message(cursor, fk_task_run, "ERROR", f"CSRF form submission failed: {str(e)}")

                try:
                    download_button = driver.find_element(By.XPATH, "//input[@type='button' and @value='Download Documents']")
                    driver.execute_script("arguments[0].click();", download_button)
                    time.sleep(3)
                except:
                    log_message(cursor, fk_task_run, "WARNING", f"Download button not found for {filename}")

                zip_file = None
                start_time = time.time()
                while time.time() - start_time < 30:
                    zips = [f for f in os.listdir(FINAL_PDF_DIR) if f.endswith(".zip")]
                    if zips:
                        latest = max([os.path.join(FINAL_PDF_DIR, f) for f in zips], key=os.path.getctime)
                        if not os.path.exists(latest + ".crdownload"):
                            zip_file = latest
                            break
                    time.sleep(1)

                if zip_file:
                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                        zip_ref.extractall(FINAL_PDF_DIR)
                        for name in zip_ref.namelist():
                            extracted_pdf = os.path.join(FINAL_PDF_DIR, name)
                            if os.path.exists(extracted_pdf):
                                file_size = os.path.getsize(extracted_pdf)
                                if file_size < 2048:
                                    log_message(cursor, fk_task_run, "WARNING", f"Downloaded file too small (<2KB): {filename} ({file_size} bytes)")
                                    os.remove(extracted_pdf)
                                    continue

                                os.rename(extracted_pdf, dest_path)
                                rel_path = f"cases\\{fk_case}\\{filename}"
                                cursor.execute("""
                                    UPDATE docketwatch.dbo.documents
                                    SET rel_path = ?, date_downloaded = GETDATE()
                                    WHERE doc_uid = ?
                                """, (rel_path, doc_uid))
                                conn.commit()
                                log_message(cursor, fk_task_run, "INFO", f"Downloaded and saved: {filename} ({file_size} bytes)")

                    os.remove(zip_file)
                else:
                    log_message(cursor, fk_task_run, "WARNING", f"ZIP not found for {filename}")

            except Exception as ex:
                log_message(cursor, fk_task_run, "ERROR", f"Download failed for {filename}: {str(ex)}")

    except Exception as e:
        log_message(cursor, None, "ERROR", f"Unhandled error: {str(e)}")
        traceback.print_exc()
    finally:
        if 'driver' in locals():
            driver.quit()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
