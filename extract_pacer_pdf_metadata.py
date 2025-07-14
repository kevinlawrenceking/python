import sys, argparse, pyodbc, os, time, traceback, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from scraper_base import log_message, setup_logging, get_db_cursor, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

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
        filename = f"E{doc_id}.pdf" if doc_id else ""

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
    parser = argparse.ArgumentParser(description="Scrape and insert PACER PDF metadata into documents table.")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    try:
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET arr_de_seq_nums = 
                SUBSTRING(event_url, CHARINDEX('de_seq_num=', event_url) + 11, 
                        CHARINDEX('&', event_url + '&', CHARINDEX('de_seq_num=', event_url)) 
                        - CHARINDEX('de_seq_num=', event_url) - 11)
            WHERE event_url IS NOT NULL
              AND arr_de_seq_nums IS NULL
              AND event_url LIKE '%de_seq_num%'
        """)
        conn.commit()

        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in DB.")
            sys.exit()
        USERNAME, PASSWORD, LOGIN_URL = row

        cursor.execute("""
            SELECT 
                c.id,
                LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
                e.event_description,
                e.event_url,
                ps.url AS pacer_site_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
            WHERE e.id = ?
        """, (args.case_event_id,))

        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "INFO", f"No event found for ID {args.case_event_id}")
            sys.exit()

        case_id, base_url, event_description, event_url, pacer_site_url = row

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
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
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'pending', GETDATE())
                    """, (case_id, args.case_event_id, 2, doc_id, event_url, event_description
                    ))
                    conn.commit()
                    log_message(cursor, fk_task_run, "INFO", f"Inserted fallback docket PDF {doc_id}")
        else:
            for i, tr in enumerate(doc_rows):
                pdf_type = "Docket" if i == 0 else "Attachment"
                doc_data = parse_doc_row(tr, base_url, pdf_type, event_description)

                # Force PACER /doc1/ URL format
                if doc_data and doc_data.get("doc_id"):
                    doc_data["pdf_url"] = pacer_site_url + "/doc1/" + str(doc_data["doc_id"])
                else:
                    continue

                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_data["doc_id"],))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
                    """, (
                        case_id, 
                        args.case_event_id, 2,
                        doc_data["doc_id"], doc_data["pdf_url"],
                        doc_data["pdf_title"], doc_data["pdf_type"],
                        doc_data["pdf_no"], doc_data["rel_path"]
                    ))
                    inserted += 1

            conn.commit()
            log_message(cursor, fk_task_run, "INFO", f"Inserted metadata for {inserted} documents.")

    except Exception as e:
        log_message(cursor, None, "ERROR", f"Unhandled error: {str(e)}")
        traceback.print_exc()
    finally:
        if 'driver' in locals():
            driver.quit()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    main()
