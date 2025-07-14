
import time
import pyodbc
import os
import sys
import logging
import psutil
import random
import unicodedata
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import traceback

# Email setup (not used for hearings, kept for future extension)
FROM_EMAIL = "it@tmz.com"
TO_EMAILS = ["Kevin.King@tmz.com"]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_pacer_scraper_hearing_final.log"
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_pacer_scraper_hearing_final.lock"
script_filename = os.path.splitext(os.path.basename(__file__))[0]

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def is_another_instance_running():
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "r") as f:
            try:
                pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    return True
            except ValueError:
                pass
        os.remove(LOCK_FILE)
    return False

def human_pause(min_time=1, max_time=3):
    time.sleep(random.uniform(min_time, max_time))

def clean_text(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text).replace("'", "''").replace("\n", " ").replace("\r", " ")
    return text[:4000]

def log_message(cursor, fk_task_run, log_type, message, fk_case=None):
    logging.info(message)
    if fk_task_run:
        try:
            if fk_case:
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description, fk_case)
                    OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?, ?)
                """, (fk_task_run, log_type, message, fk_case))
            else:
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                    OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?)
                """, (fk_task_run, log_type, message))
            return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"Logging failed: {e}")
    return None

# Placeholder for docketwatch_pacer_scraper_hearing_cleaned.py

def scrape_hearings(driver, case_url, fk_case, case_name, cursor, fk_task_run):
    inserted = 0
    try:
        driver.get(case_url)
        human_pause(3, 5)

        # Click the "Deadlines/Hearings..." link
        try:
            link = driver.find_element(By.PARTIAL_LINK_TEXT, "Deadlines/Hearings")
            link.click()
            human_pause(2, 4)

            # Click "Run Query" to load the table
            driver.find_element(By.XPATH, "//input[@value='Run Query']").click()
            human_pause(2, 4)
        except Exception as e:
            log_message(cursor, fk_task_run, "WARNING", f"No Hearings form found: {e}", fk_case=fk_case)
            return 0

        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find("table", {"border": "1"})
        if not table:
            log_message(cursor, fk_task_run, "INFO", f"No hearings table found for {case_name}.", fk_case=fk_case)
            return 0


        rows = table.find_all("tr")[1:]  # skip header row
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            try:
                calendar_number = cols[0].get_text(strip=True)
                doc_link_tag = cols[0].find("a")
                doc_url = doc_link_tag["href"] if doc_link_tag else None

                hearing_type = cols[1].get_text(strip=True)
                due_date_text = cols[3].get_text(strip=True)
                satisfied = cols[4].get_text(strip=True)
                terminated = cols[5].get_text(strip=True)

                # Skip if date is invalid or in the past
                hearing_datetime = datetime.strptime(due_date_text, "%m/%d/%Y")
                if hearing_datetime <= datetime.today():
                    continue

                # Check for duplicate
                cursor.execute("""
                    SELECT COUNT(*) FROM docketwatch.dbo.hearings
                    WHERE fk_case = ? AND hearing_datetime = ? AND calendar_number = ? AND terminated = ?
                """, (fk_case, hearing_datetime, calendar_number, terminated))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.hearings
                        (fk_case, calendar_number, doc_url, hearing_type, hearing_datetime, satisfied, terminated, fk_task_run)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (fk_case, calendar_number, doc_url, hearing_type, hearing_datetime, satisfied, terminated, fk_task_run))
                    inserted += 1

            except Exception as e:
                log_message(cursor, fk_task_run, "WARNING", f"Row parse failed: {e}", fk_case=fk_case)

        cursor.connection.commit()
        log_message(cursor, fk_task_run, "ALERT" if inserted else "INFO", f"Inserted {inserted} hearings for {case_name}", fk_case=fk_case)
        return inserted

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Exception during hearing scrape for {case_name}: {str(e)}", fk_case=fk_case)
        return 0


def main():

    if is_another_instance_running():
        logging.error("Another instance is already running. Exiting...")
        return
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    cursor.execute("SELECT id, fk_tool FROM docketwatch.dbo.scheduled_task WHERE filename = ?", (script_filename,))
    row = cursor.fetchone()
    if not row:
        print("Scheduled task not found.")
        return

    scheduled_task_id, fk_tool = row

    cursor.execute("""
        INSERT INTO docketwatch.dbo.task_runs (fk_scheduled_task, fk_tool, timestamp_started, status)
        OUTPUT INSERTED.id
        VALUES (?, ?, GETDATE(), 'Started')
    """, (scheduled_task_id, fk_tool))
    fk_task_run = cursor.fetchone()[0]
    conn.commit()

    cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
    USERNAME, PASSWORD, LOGIN_URL = cursor.fetchone()

    try:
        CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless=new")

        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(LOGIN_URL)
        human_pause(2, 4)

        driver.find_element(By.NAME, "loginForm:loginName").send_keys(USERNAME)
        human_pause(1, 2)

        driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
        human_pause(1, 2)

        # Fill in Client Code
        try:
            client_code_input = driver.find_element(By.NAME, "loginForm:clientCode")
            client_code_input.clear()
            client_code_input.send_keys("DocketWatch")
            human_pause(1, 2)
            log_message(cursor, fk_task_run, "INFO", "Client Code 'DocketWatch' entered successfully")
        except Exception as e:
            log_message(cursor, fk_task_run, "WARNING", f"Client Code field not found or could not be filled: {e}")

        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        human_pause(3, 5)

        log_message(cursor, fk_task_run, "INFO", "PACER login successful")


        cursor.execute("""
            SELECT c.id, c.case_name, c.case_url
            FROM docketwatch.dbo.cases c
            WHERE c.fk_tool = 2 and c.status = 'Tracked'
        """)

        for fk_case, case_name, case_url in cursor.fetchall():
            scrape_hearings(driver, case_url, fk_case, case_name, cursor, fk_task_run)

        cursor.execute("UPDATE docketwatch.dbo.task_runs SET timestamp_ended = GETDATE(), status = 'Completed' WHERE id = ?", (fk_task_run,))
        conn.commit()
        log_message(cursor, fk_task_run, "INFO", "PACER Hearings Scraper Completed")

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Script failed: {str(e)}")
        traceback.print_exc()
    finally:
        driver.quit()
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
