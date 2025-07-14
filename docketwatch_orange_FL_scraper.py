# Orange County FL Scraper – TOOL_ID 25
# Filename: docketwatch_orange_FL_scraper.py

import os
import sys
import time
import traceback
import pyodbc
import logging
import random
import string
import requests

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Constants
TOOL_ID = 25
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# Logging
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# DB Connection
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

# Get 2Captcha API key
cursor.execute("SELECT captcha_api FROM docketwatch.dbo.utilities WHERE id = 1;")
captcha_row = cursor.fetchone()
captcha_api_key = captcha_row[0] if captcha_row else None

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
        except:
            return None
    return None

def solve_recaptcha_2captcha(api_key, site_key, page_url):
    payload = {
        'key': api_key,
        'method': 'userrecaptcha',
        'googlekey': site_key,
        'pageurl': page_url,
        'json': 1
    }
    response = requests.post("http://2captcha.com/in.php", data=payload).json()
    if response.get("status") != 1:
        raise Exception("2Captcha request failed: " + response.get("request", ""))

    captcha_id = response["request"]
    for _ in range(20):
        time.sleep(3)
        check = requests.get(f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1").json()
        if check.get("status") == 1:
            return check["request"]
    raise Exception("2Captcha timeout waiting for solution")

def insert_case_events(driver, fk_case, case_name, case_number):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    event_table = soup.find("table", {"summary": "docket events"})
    if not event_table:
        log_message("INFO", f"No events for {case_number}")
        return

    inserted = 0
    for row in event_table.find("tbody").find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 2: continue
        event_date = cols[0].text.strip()
        description = cols[1].text.strip()
        extra = ""

        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_description = ? AND event_date = ?
        """, (fk_case, description, event_date))
        exists = cursor.fetchone()[0]
        if not exists:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_events (fk_cases, event_date, event_description, additional_information, fk_task_run_log)
                VALUES (?, ?, ?, ?, ?)
            """, (fk_case, event_date, description, extra, fk_task_run))
            inserted += 1

    log_message("INFO", f"Inserted {inserted} event(s) for {case_number}")
    conn.commit()

def update_case_and_tool_case(case_id, case_number, search_url, fk_county):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)

    try:
        driver.get(search_url)
        time.sleep(2)
        log_message("INFO", "Chrome launched and initial page loaded.")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "caseNumber"))).send_keys(case_number)

        # Solve CAPTCHA
        recaptcha_div = driver.find_element(By.XPATH, "//div[@class='g-recaptcha']")
        sitekey = recaptcha_div.get_attribute("data-sitekey")
        token = solve_recaptcha_2captcha(captcha_api_key, sitekey, search_url)

        driver.execute_script("document.getElementById('g-recaptcha-response').style.display = 'block';")
        driver.execute_script("document.getElementById('g-recaptcha-response').value = arguments[0];", token)
        time.sleep(2)

        search_button = driver.find_element(By.ID, "caseSearch")
        driver.execute_script("arguments[0].disabled = false;", search_button)
        search_button.click()

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "caseList")))
        first_row = driver.find_element(By.CSS_SELECTOR, "#caseList tbody tr")
        link = first_row.find_element(By.CSS_SELECTOR, "td.colCaseNumber a.caseLink")

        # Get basic data before clicking
        case_name = first_row.find_elements(By.TAG_NAME, "td")[2].text.strip()
        case_type = first_row.find_elements(By.TAG_NAME, "td")[3].text.strip()

        # Hardcode court_code = 'OCFL'
        fk_court = 'OCFL'
        log_message("INFO", f"Assigned fk_court: {fk_court}")

        # Click the case link to navigate (not .get())
        link.click()
        time.sleep(3)

        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET case_number = ?, case_name = ?, fk_tool = ?, status = 'Tracked', case_type = ?, fk_court = ?, fk_task_run_log = ?, last_updated = GETDATE()
            WHERE id = ?
        """, (case_number, case_name, TOOL_ID, case_type, fk_court, fk_task_run, case_id))

        conn.commit()
        insert_case_events(driver, case_id, case_name, case_number)
        print(f"UPDATED_CASE_ID={case_id}")
    except Exception as e:
        log_message("ERROR", f"Error processing case {case_id}: {str(e)}")
        traceback.print_exc()
    finally:
        driver.quit()

def main():
    log_message("INFO", "Orange scraper started")
    try:
        if len(sys.argv) > 1 and sys.argv[1].isdigit():
            log_message("INFO", f"Single-case mode: case ID = {sys.argv[1]}")
            case_id = int(sys.argv[1])
            cursor.execute("SELECT case_number FROM docketwatch.dbo.cases WHERE id = ?", (case_id,))
            case_number = cursor.fetchone()[0]
            cursor.execute("SELECT search_url, fk_county FROM docketwatch.dbo.tools WHERE id = ?", (TOOL_ID,))
            tool_row = cursor.fetchone()
            update_case_and_tool_case(case_id, case_number, tool_row[0], tool_row[1])
        else:
            log_message("INFO", "Bulk mode – querying tracked cases...")
            cursor.execute("""
                SELECT c.id, c.case_number, t.case_url, too.search_url, too.fk_county
                FROM docketwatch.dbo.cases c
                INNER JOIN docketwatch.dbo.tools too ON too.id = c.fk_tool
                WHERE c.status = 'Tracked' AND t.fk_tool = ?
            """, (TOOL_ID,))
            rows = cursor.fetchall()
            log_message("INFO", f"Found {len(rows)} tracked cases")
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
