import os
import sys
import time
import logging
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pyodbc

# === Setup Paths & Imports ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# === Database Connection ===
def get_db_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    return conn, conn.cursor()

# === Logging ===
def setup_logging():
    log_path = fr"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")

def log_message(cursor, fk_task_run, log_type, message):
    logging.info(message)
    if not cursor or not fk_task_run:
        return
    try:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
            VALUES (?, GETDATE(), ?, ?)
        """, (fk_task_run, log_type, message))
        cursor.connection.commit()
    except Exception as ex:
        logging.warning(f"Failed to write to task_runs_log: {ex}")

# === PACER Login Reuse ===
def perform_pacer_login(driver, cookie_string):
    driver.get("https://ecf.alsd.uscourts.gov")
    driver.add_cookie({'.AspNetCore.Cookies': cookie_string})
    driver.get("https://ecf.alsd.uscourts.gov/cgi-bin/login.pl")
    time.sleep(2)

# === Insert Hearings ===
def insert_hearing(cursor, fk_case, hearing_type, hearing_datetime, event_filed, satisfied, terminated, doc_url):
    cursor.execute("""
        SELECT COUNT(*) FROM docketwatch.dbo.hearings
        WHERE fk_case = ? AND hearing_datetime = ?
    """, (fk_case, hearing_datetime))
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.hearings 
            (fk_case, hearing_type, hearing_datetime, event_filed, satisfied, terminated, doc_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fk_case, hearing_type, hearing_datetime, event_filed, satisfied, terminated, doc_url))
        cursor.connection.commit()
        return True
    return False

# === Scrape Hearings ===
def scrape_hearings(driver, case_url, fk_case, cursor):
    driver.get(case_url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Deadlines/Hearings"))).click()
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@value='Run Query']"))).click()
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    rows = soup.find_all("tr")[1:]  # Skip header

    inserted = 0
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        hearing_type = cols[1].get_text(strip=True)
        if "hearing" not in hearing_type.lower():
            continue

        due_date_text = cols[3].get_text(strip=True)
        try:
            hearing_datetime = datetime.strptime(due_date_text, "%m/%d/%Y")
            if hearing_datetime <= datetime.today():
                continue
        except:
            continue

        doc_url = cols[0].find("a")["href"]
        full_doc_url = f"https://ecf.alsd.uscourts.gov{doc_url}" if not doc_url.startswith("http") else doc_url
        event_filed = cols[2].get_text(strip=True)
        satisfied = cols[4].get_text(strip=True)
        terminated = cols[5].get_text(strip=True)

        if insert_hearing(cursor, fk_case, hearing_type, hearing_datetime, event_filed, satisfied, terminated, full_doc_url):
            inserted += 1
    return inserted

# === Main ===
def main():
    setup_logging()
    conn, cursor = get_db_cursor()
    cursor.execute("SELECT id FROM docketwatch.dbo.scheduled_task WHERE filename = ?", (script_filename,))
    row = cursor.fetchone()
    if not row:
        print("Scheduled task not found.")
        return
    scheduled_task_id = row[0]
    cursor.execute("INSERT INTO docketwatch.dbo.task_runs (fk_scheduled_task, timestamp_started, status) OUTPUT INSERTED.id VALUES (?, GETDATE(), 'Started')", (scheduled_task_id,))
    fk_task_run = cursor.fetchone()[0]
    conn.commit()

    log_message(cursor, fk_task_run, "INFO", "=== PACER Hearings Scraper Started ===")

    # Set up browser
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

    try:
        # Reuse PACER cookie session if applicable
        perform_pacer_login(driver, "your_cookie_here")  # Replace with actual method

        cursor.execute("""
            SELECT top 1 c.id, c.case_number, t.case_url 
            FROM docketwatch.dbo.cases c
            WHERE c.status = 'Tracked' AND c.fk_priority = 4 AND c.fk_tool = 2
        """)
        for case_id, case_number, case_url in cursor.fetchall():
            try:
                count = scrape_hearings(driver, case_url, case_id, cursor)
                log_message(cursor, fk_task_run, "INFO", f"{count} hearings inserted for case {case_number}")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Failed on case {case_number}: {e}")
                traceback.print_exc()

        cursor.execute("UPDATE docketwatch.dbo.task_runs SET timestamp_ended = GETDATE(), status = 'Completed' WHERE id = ?", (fk_task_run,))
        conn.commit()
        log_message(cursor, fk_task_run, "INFO", "=== PACER Hearings Scraper Completed ===")
    finally:
        driver.quit()
        cursor.close()
        conn.close()

main()
