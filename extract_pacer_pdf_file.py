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

def main():
    parser = argparse.ArgumentParser(description="Download PACER PDF using stored pdf_url")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    try:
        conn, cursor = get_db_cursor()
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
            SELECT c.id AS fk_case,
                   d.doc_id,
                   d.doc_uid,
                   d.pdf_url,
                   d.pdf_type,
                   d.pdf_title
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
            INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            WHERE d.fk_case_event = ? AND d.rel_path = 'pending'
        """, (args.case_event_id,))
        rows = cursor.fetchall()
        if not rows:
            log_message(cursor, fk_task_run, "INFO", "No pending documents to download.")
            return

        opts = Options()
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

        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.NAME, "loginForm:loginName"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
        try:
            driver.find_element(By.NAME, "loginForm:clientCode").send_keys("DocketWatch")
        except:
            pass
        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        time.sleep(3)

        for row in rows:
            doc_id = row.doc_id
            doc_uid = row.doc_uid
            pdf_url = row.pdf_url
            fk_case = row.fk_case
            filename = f"E{doc_id}.pdf"
            case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
            os.makedirs(case_dir, exist_ok=True)
            dest_path = os.path.join(case_dir, filename)

            try:
                log_message(cursor, fk_task_run, "INFO", f"Navigating to PDF URL: {pdf_url}")
                driver.get(pdf_url)
                time.sleep(10)  # wait for the PDF to load or trigger download

                rel_path = f"cases\\{fk_case}\\{filename}"
                cursor.execute("""
                    UPDATE docketwatch.dbo.documents
                    SET rel_path = ?, date_downloaded = GETDATE()
                    WHERE doc_uid = ?
                """, (rel_path, doc_uid))
                conn.commit()
                log_message(cursor, fk_task_run, "INFO", f"Marked PDF as downloaded: {filename}")

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
