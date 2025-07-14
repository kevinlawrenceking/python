import os
import json
import pyodbc
import time
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === GET SCRIPT NAME ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# === DATABASE CONNECTION & TASK RUN ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("""
    SELECT TOP 1 r.id as fk_task_run 
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
    WHERE s.filename = ? 
    ORDER BY r.id DESC
""", (script_filename,))
task_run = cursor.fetchone()
fk_task_run = task_run[0] if task_run else None

# === LOGGING SETUP ===
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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
        except Exception as e:
            print(f"Database Logging Error: {str(e)}")
            return None
log_message("INFO", "=== LaCourt API Auth + Scraper Started ===")

# === Setup ChromeDriver ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)
log_message("INFO", "ChromeDriver initialized.")

# === Fetch credentials and URLs from DB (tool id = 6) ===
cursor.execute("""
    SELECT [login_url], [username], [pass], [search_url]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = 6
""")
login_url, username, password, _ = cursor.fetchone()
log_message("INFO", "Fetched login credentials from database.")

# === Step 1: Log into the page ===
log_message("INFO", "Navigating to login page...")
driver.get(login_url)
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "next"))).click()
time.sleep(5)
log_message("INFO", "Login submitted.")

# === Step 2: Extract .AspNetCore.Cookies ===
cookies = driver.get_cookies()
cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
driver.quit()
log_message("INFO", "Extracted auth cookie from session.")

# === Fetch cases records ===
cursor.execute("""
    SELECT [case_number], [map_id], id as [fk_case],[case_name]
    FROM [docketwatch].[dbo].[cases]
    WHERE fk_tool = 6 and status = 'Tracked'
""")
tool_cases = cursor.fetchall()

for case_number, map_id, fk_case, case_name in tool_cases:
    log_message("INFO", f"Processing case: {case_name}")

    # Make API call
    headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}
    api_url = f"https://media.lacourt.org/api/AzureApi/GetCaseDetail/{map_id}"
    log_message("INFO", f"Making API request to {api_url}")
    response = requests.get(api_url, headers=headers)

    try:
        data = response.json()
    except Exception as e:
        log_message("ERROR", f"Failed to parse JSON for case {case_number}: {str(e)}")
        continue

    # Insert RegisterOfActions
    actions = data.get("ResultList", [])[0].get("NonCriminalCaseInformation", {}).get("RegisterOfActions", [])
    for action in actions:
        event_date = action.get("RegisterOfActionDateString", "").strip()
        event_description = action.get("Description", "").strip()
        additional_information = action.get("AdditionalInformation", "").strip()

        if not event_date or not event_description:
            continue

        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_description = ? AND event_date = ?
        """, (fk_case, event_description, event_date))
        exists = cursor.fetchone()[0]

        if exists:
            continue

        cursor.execute("""
            INSERT INTO docketwatch.dbo.case_events (event_date, event_description, additional_information, fk_cases)
            VALUES (?, ?, ?, ?)
        """, (event_date, event_description, additional_information, fk_case))
        conn.commit()

    # === New: Update cases table ===
    header_info = data["ResultList"][0]["HeaderInformation"]
    case_info = data["ResultList"][0]["NonCriminalCaseInformation"]["CaseInformation"]

    def get_header_value(key_name):
        for item in header_info:
            if item["Key"] == key_name:
                return item["Value"]
        return None

    case_number = get_header_value("Case Number")
    case_title = get_header_value("Case Title")
    case_type_note = get_header_value("Case Type")
    filing_courthouse = get_header_value("Filing Courthouse")

    cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_name = ?", filing_courthouse)
    court_row = cursor.fetchone()
    court_code = court_row[0] if court_row else None

    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET case_name = ?, fk_court = ?, notes = ?, case_type = ?, case_url = ISNULL(case_url, ?)
        WHERE case_number = ?
    """, (case_title, court_code, case_type_note, case_info.get("LitigationTypeObject", {}).get("Description", ""), f"https://www.lacourt.org/casesummary/ui/casesummary.aspx?casetype=familylaw&casenumber={case_number}", case_number))
    conn.commit()

# Cleanup
cursor.close()
conn.close()
log_message("INFO", "Database connection closed.")
log_message("INFO", "=== LaCourt API Scraper Completed ===")