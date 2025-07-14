import sys, os, time, pyodbc, traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scraper_base import get_db_cursor, setup_logging, log_message, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"

def download_pending_documents_for_event(cursor, driver, wait, case_event_id, fk_task_run):
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.doc_id,
            c.id AS fk_case,
            ps.url + '/cgi-bin/show_multidocs.pl?caseid=' + 
                CAST(c.pacer_id AS VARCHAR) +
                '&arr_de_seq_nums=' + CAST(e.arr_de_seq_nums AS VARCHAR) +
                '&pdf_header=2&pdf_toggle_possible=1&zipit=1' AS download_url
        FROM docketwatch.dbo.documents d
        INNER JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
        INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
        WHERE d.fk_case_event = ? AND d.rel_path = 'pending'
    """, (case_event_id,))
    rows = cursor.fetchall()
    if not rows:
        return 0

    inserted = 0
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
            log_message(cursor, fk_task_run, "INFO", f"Opening: {download_url}")
            driver.get(download_url)
            time.sleep(2)

            if "referrer_form" in driver.page_source:
                form = driver.find_element(By.ID, "referrer_form")
                driver.execute_script("arguments[0].submit();", form)
                time.sleep(3)

            try:
                button = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='View Document']")))
                button.click()
                time.sleep(5)
            except:
                log_message(cursor, fk_task_run, "WARNING", f"View Document button not found for {filename}")
                continue

            # Wait for the download to complete
            zip_file = None
            start_time = time.time()
            while time.time() - start_time < 30:
                pdfs = [f for f in os.listdir(FINAL_PDF_DIR) if f.lower().endswith(".pdf") and filename in f]
                if pdfs:
                    latest = os.path.join(FINAL_PDF_DIR, pdfs[0])
                    if not os.path.exists(latest + ".crdownload"):
                        zip_file = latest
                        break
                time.sleep(1)

            if zip_file:
                os.rename(zip_file, dest_path)
                rel_path = f"cases\\{fk_case}\\{filename}"
                cursor.execute("""
                    UPDATE docketwatch.dbo.documents
                    SET rel_path = ?, date_downloaded = GETDATE()
                    WHERE doc_uid = ?
                """, (rel_path, doc_uid))
                cursor.connection.commit()
                inserted += 1
                log_message(cursor, fk_task_run, "INFO", f"Downloaded and saved: {filename}")
            else:
                log_message(cursor, fk_task_run, "WARNING", f"PDF not found for {filename}")

        except Exception as e:
            log_message(cursor, fk_task_run, "ERROR", f"Download error for {filename}: {str(e)}")

    return inserted

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download PACER PDFs for a given case_event_id")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    try:
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
        wait = WebDriverWait(driver, 15)

        inserted = download_pending_documents_for_event(cursor, driver, wait, args.case_event_id, fk_task_run)
        log_message(cursor, fk_task_run, "INFO", f"Total documents downloaded: {inserted}")

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
