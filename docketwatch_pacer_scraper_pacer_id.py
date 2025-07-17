
# docketwatch_pacer_scraper_pacer_id.py
# Scrapes a single PACER case by PACER ID and inserts docket events

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
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from scraper_base import (
    extract_and_store_pacer_billing,
    mark_case_not_found,
    mark_case_found,
    log_message
)

FROM_EMAIL = "it@tmz.com"
TO_EMAILS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "marlee.chartash@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_pacer_scraper_pacer_id.log"
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_pacer_scraper_pacer_id.lock"
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

def send_docket_email(case_name, case_url, event_no, cleaned_docket_text):
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib

    subject = f"DocketWatch Alert: {case_name} – New Docket Discovered"
    body = f"""
    <html>
    <body>
        A new docket has been detected for case:<br>
        <a href=\"{case_url}\">{case_name}</a><br><br>
        <strong>Docket No:</strong> {event_no}<br>
        <strong>Description:</strong><br>
        <p>{cleaned_docket_text}</p>
    </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        log_message(cursor, fk_task_run, "ALERT", f"Email sent for new docket in case {case_name}", fk_case=None)
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Failed to send email for case {case_name}: {e}", fk_case=None)

def main():
    global conn, cursor, driver, fk_task_run

    if len(sys.argv) < 2:
        print("Usage: python docketwatch_pacer_scraper_pacer_id.py <PACER_ID>")
        return

    try:
        PACER_ID = int(sys.argv[1])
    except ValueError:
        print("Invalid PACER_ID. Must be integer.")
        return

    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.id as fk_task_run 
        FROM docketwatch.dbo.task_runs r
        INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
        WHERE s.filename = ? 
        ORDER BY r.id DESC
    """, (script_filename,))
    task_run = cursor.fetchone()
    fk_task_run = task_run[0] if task_run else None

    log_message(cursor, fk_task_run, "INFO", f"=== PACER Scraper (Single Case by PACER_ID: {PACER_ID}) Started ===")

    if is_another_instance_running():
        log_message(cursor, fk_task_run, "ERROR", "Another instance is already running. Exiting...")
        return
    else:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

    cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
    USERNAME, PASSWORD, LOGIN_URL = cursor.fetchone()

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service("C:/WebDriver/chromedriver.exe"), options=options)

    driver.get(LOGIN_URL)
    human_pause(2, 4)
    driver.find_element(By.NAME, "loginForm:loginName").send_keys(USERNAME)
    driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
    try:
        client_code_input = driver.find_element(By.NAME, "loginForm:clientCode")
        client_code_input.clear()
        client_code_input.send_keys("DocketWatch")
    except:
        pass
    driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
    human_pause(3, 5)

    cursor.execute("""
        SELECT c.id, c.id as fk_case, c.case_url, c.case_name, c.case_number
        FROM docketwatch.dbo.cases c
        WHERE c.fk_tool = 2 AND c.status = 'Tracked' AND c.pacer_id = ?
    """, (PACER_ID,))
    cases = cursor.fetchall()

    if not cases:
        log_message(cursor, fk_task_run, "WARNING", f"No case found with PACER ID {PACER_ID}")
        return

    for case in cases:
        case_id, fk_case, case_url, case_name, case_number = case
        log_id = log_message(cursor, fk_task_run, "INFO", f"Reviewing case: {case_name}", fk_case=fk_case)
        cursor.execute("UPDATE dbo.cases SET fk_task_run_log = ? WHERE id = ?", (log_id, case_id))
        conn.commit()

        try:
            driver.get(case_url)
            human_pause(3, 5)
            driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report").click()
            human_pause(3, 5)
            driver.find_element(By.XPATH, '//input[@name="date_range_type" and @value="Filed"]').click()
            driver.find_element(By.NAME, "date_from").clear()
            driver.find_element(By.NAME, "date_from").send_keys((datetime.today() - timedelta(days=5)).strftime("%m/%d/%Y"))
            driver.find_element(By.NAME, "date_to").clear()
            driver.find_element(By.NAME, "date_to").send_keys((datetime.today() + timedelta(days=5)).strftime("%m/%d/%Y"))
            for checkbox_id in ["list_of_parties_and_counsel", "terminated_parties"]:
                try:
                    checkbox = driver.find_element(By.ID, checkbox_id)
                    if checkbox.is_selected():
                        checkbox.click()
                except:
                    pass
            try:
                Select(driver.find_element(By.NAME, "sort1")).select_by_visible_text("Most recent date first")
            except:
                pass
            human_pause(1, 2)
            driver.find_element(By.NAME, "button1").click()
            human_pause(3, 5)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            extract_and_store_pacer_billing(soup, cursor, fk_case, fk_task_run)
            mark_case_found(cursor, fk_case)

            docket_rows = driver.find_elements(By.XPATH, "//table[@border='1']/tbody/tr")
            for row in docket_rows[1:]:
                columns = row.find_elements(By.TAG_NAME, "td")
                if len(columns) < 3:
                    continue
                event_date = columns[0].text.strip()
                docket_number_text = columns[1].text.strip()
                docket_text = columns[2].text.strip()
                event_no = int(docket_number_text) if docket_number_text.isdigit() else 0
                cleaned_docket_text = clean_text(docket_text)

                cursor.execute("""
                    SELECT COUNT(*) FROM dbo.case_events 
                    WHERE event_date = ? AND LEFT(event_description, 100) = ? AND fk_cases = ?
                """, (event_date, cleaned_docket_text[:100], fk_case))
                exists = cursor.fetchone()[0]

                if not exists:
                    log_id = log_message(cursor, fk_task_run, "ALERT", f"New docket discovered! Docket added to case {case_name}", fk_case=fk_case)
                    cursor.execute("""
                        INSERT INTO dbo.case_events (
                            event_date, event_no, event_description, fk_cases, status, fk_task_run_log
                        ) VALUES (?, ?, ?, ?, 'RSS', ?)
                    """, (event_date, event_no, cleaned_docket_text, fk_case, log_id))
                    conn.commit()
                    send_docket_email(case_name, case_url, event_no, cleaned_docket_text)
                else:
                    log_message(cursor, fk_task_run, "INFO", f"Docket number {event_no} already exists for case {case_name}", fk_case=fk_case)

        except Exception as e:
            log_message(cursor, fk_task_run, "ERROR", f"Docket scraping failed: {e}", fk_case=fk_case)
            mark_case_not_found(cursor, fk_case, fk_task_run)
            continue

if __name__ == "__main__":
    driver = None
    try:
        main()
    finally:
        try: log_message(cursor, fk_task_run, "INFO", "PACER Scraper Completed Successfully")
        except: pass
        try: cursor.close()
        except: pass
        try: conn.close()
        except: pass
        try: driver.quit()
        except: pass
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except: pass
