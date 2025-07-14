"""
DocketWatch Scraper Template – Base Script for Tool Integration
===============================================================

This script is designed as a **template for building new court scraper integrations** 
into the DocketWatch system. It provides all the shared functionality needed across 
tools, with only minimal adjustments required for site-specific behavior.

Core Features Included:
------------------------
 Database connection via ODBC (uses DSN "Docketwatch")
 Logs actions to `task_runs_log` with `fk_task_run` linkage
 Handles both:
    • Looping tracked cases (counter mode)
    • Single-case lookup via command line parameter (case_id)
 Scrapes case events and inserts only **new** records into `case_events`
 Populates `cases`, `tool_cases`, and `courts` with normalized fields
 Dynamically logs summaries and updates related tables
 Outputs `UPDATED_CASE_ID` (if parameter used) to pass back to ColdFusion or UI

Where to Customize for a New Tool:
----------------------------------
 TOOL_ID – Update this to the tool’s ID in the `tools` table  
 DOM interaction logic (clicks, form input, etc.)
    – Update in `update_case_and_tool_case()` and `insert_case_events()`  
 HTML parsing logic – Tailor `extract_case_name_from_html()` and `extract_court_and_type()`

Required Table Fields (assumed by logic):
-----------------------------------------
• `tools.search_url` → Base page for scraper to start on
• `tools.fk_county` → Used to link courts and assign `fk_court`
• `courts.court_name` (text match) → Checked or inserted if missing
• `cases.case_number`, `case_name`, `fk_court`, `case_type` – updated with scraped data
• `tool_cases.case_number`, `case_name`, `case_url`, `fk_task_run_log` – updated per tool

Usage:
------
• Loop all tracked cases for tool:
    ```bash
    python docketwatch_tool_scraper.py
    ```

• Run single-case update (e.g., after inserting via UI):
    ```bash
    python docketwatch_tool_scraper.py 12345
    ```

Note: Replace `docketwatch_tool_scraper.py` with the actual script name.  
      `12345` is the `cases.id` value.

Deployment Notes:
------------------
• Script expects ChromeDriver and Selenium installed  
• Assumes `fk_tool = TOOL_ID` is set properly in `tool_cases`
• Uses `--headless=new` to avoid GUI pop-ups in production
• Requires court websites to be publicly accessible or VPN-enabled

Author:
-------
This template was created with guidance from ChatGPT to streamline court scraping 
for multiple jurisdictions. Copy, reuse, and modify freely within the DocketWatch project.
"""

import os
import sys
import time
import traceback
import pyodbc
import logging
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Constants
TOOL_ID = 13
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

# Logging
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_broward_scraper.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# Email Settings
FROM_EMAIL = "it@tmz.com"
TO_EMAIL = "kevin.king@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

# Database connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
conn.setencoding(encoding='utf-8')
cursor = conn.cursor()

# Get current task run
cursor.execute("""
    SELECT TOP 1 r.id as fk_task_run 
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
    WHERE s.filename = ? 
    ORDER BY r.id DESC
""", (script_filename,))
task_run = cursor.fetchone()
fk_task_run = task_run[0] if task_run else None

def log_message(log_type, message):
    logging.info(message)
    if fk_task_run:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?)
            """, (fk_task_run, log_type, message))
            log_id = cursor.fetchone()[0]
            conn.commit()
            return log_id
        except pyodbc.Error as e:
            print(f"Database Logging Error: {str(e)}")
            return None
    return None

def generate_random_code(length=5):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def extract_case_name_from_html(page_source):
    try:
        soup = BeautifulSoup(page_source, "html.parser")
        header_div = soup.find("div", {"id": "styleHeader"})
        if header_div:
            return header_div.get_text(strip=True)
    except Exception as e:
        log_message("WARNING", f"Failed to extract case name from detail page: {e}")
    return "Unknown"

def extract_court_and_type(soup, fk_county, cursor, conn=None):
    import logging

    court_name = ""
    case_type = ""
    fk_court = None

    court_span = soup.find("span", {"id": "liCRCourtLocation"}) or soup.find("span", {"id": "liCourtLocationNotCR"})
    if court_span:
        court_name = court_span.get_text(strip=True)
        cursor.execute("""
            SELECT court_code FROM docketwatch.dbo.courts
            WHERE fk_county = ? AND court_name = ?
        """, (fk_county, court_name))
        result = cursor.fetchone()
        if result:
            fk_court = result[0]
        else:
            logging.warning(f"[NO MATCH] Court not found in DB: '{court_name}' (fk_county: {fk_county}) — skipping insert.")

    type_span = soup.find("span", {"id": "liCaseType"})
    if type_span:
        case_type = type_span.get_text(strip=True)

    return fk_court, case_type


def update_case_and_tool_case(case_id, case_number, search_url, fk_county):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)

    try:
        log_id = log_message("INFO", f"Opening browser to: {search_url.strip()}")
        driver.get(search_url.strip())
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="#caseNumberSearch"]'))).click()
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "CaseNumber"))).send_keys(case_number)
        driver.find_element(By.ID, "CaseNumberSearchResults").click()
        time.sleep(5)
        driver.find_element(By.CLASS_NAME, "bc-casedetail-viewer").click()
        time.sleep(5)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        case_name = extract_case_name_from_html(page_source)
        fk_court, case_type = extract_court_and_type(soup, fk_county)

        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET case_number = ?, case_name = ?, fk_tool = ?, status = 'Tracked', fk_court = ?, case_type = ?, fk_task_run_log = ?
            WHERE id = ?
        """, (case_number, case_name, TOOL_ID, fk_court, case_type, log_id, case_id))

        conn.commit()
        log_message("INFO", f"Case ID {case_id} updated successfully.")
        print(f"UPDATED_CASE_ID={case_id}")

        insert_case_events(driver, case_id, case_name, case_number)
    except Exception as e:
        log_message("ERROR", f"Error updating case {case_id}: {e}")
    finally:
        driver.quit()

def insert_case_events(driver, fk_case, case_name, case_number):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    event_table = soup.find("table", {"id": "tblEvents"})
    if not event_table:
        log_message("INFO", f"No events table found for {case_number}")
        return

    inserted = 0
    summary_log = []
    for row in event_table.find("tbody").find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        event_date = cols[0].text.strip()
        description = cols[1].text.strip()
        extra = cols[2].text.strip()
        full_description = f"{description} | {extra}" if extra else description

        exists_params = (fk_case, full_description, event_date)
        insert_params = (fk_case, event_date, full_description, extra, fk_task_run)

        cursor.execute("""
        SELECT COUNT(*) FROM docketwatch.dbo.case_events
        WHERE fk_cases = ? AND event_description = ? AND event_date = ?
        """, exists_params)
        exists = cursor.fetchone()[0]
        if not exists:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_events (fk_cases, event_date, event_description, additional_information, fk_task_run_log)
                VALUES (?, ?, ?, ?, ?)
            """, insert_params)
            inserted += 1
            summary_log.append(f"New event for {case_name}: {full_description}")

    if inserted:
        summary = "\n".join(summary_log)
        log_message("ALERT", f"Summary of inserted events for {case_name}:\n" + summary)
    log_message("INFO", f"Inserted {inserted} event(s) for {case_number}")
    conn.commit()

def main():
    log_message("INFO", "Broward scraper started")
    try:
        if len(sys.argv) > 1 and sys.argv[1].isdigit():
            cursor.execute("SELECT case_number FROM docketwatch.dbo.cases WHERE id = ?", (int(sys.argv[1]),))
            row = cursor.fetchone()
            if not row:
                log_message("ERROR", f"Case ID {sys.argv[1]} not found in database.")
                return
            case_number = row[0]
            cursor.execute("SELECT search_url, fk_county FROM docketwatch.dbo.tools WHERE id = ?", (TOOL_ID,))
            tool_row = cursor.fetchone()
            search_url = tool_row[0]
            fk_county = tool_row[1]
            update_case_and_tool_case(int(sys.argv[1]), case_number, search_url, fk_county)
        else:
            cursor.execute("""
                SELECT c.id, c.case_number, c.case_url, too.search_url, too.fk_county
                FROM docketwatch.dbo.cases c
              
                INNER JOIN docketwatch.dbo.tools too ON too.id = c.fk_tool
                WHERE c.status = 'Tracked' AND t.fk_tool = ? AND c.case_url IS NOT NULL  
            """, (TOOL_ID,))
            rows = cursor.fetchall()
            for row in rows:
                update_case_and_tool_case(row.id, row.case_number, row.search_url, row.fk_county)
    except Exception as e:
        log_message("ERROR", f"Fatal error: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
