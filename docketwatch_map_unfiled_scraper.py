import subprocess
import re
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- DocketWatch logging + DB imports ---
from scraper_base import log_message, get_task_context_by_tool_id, get_db_cursor, setup_logging

# === Set up logging file path ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]
log_path = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
setup_logging(log_path)

# === Get date param from command line ===
if len(sys.argv) < 2:
    print("Usage: python docketwatch_map_unfiled_scraper.py MM-DD-YYYY")
    sys.exit(1)

input_date = sys.argv[1]
try:
    dt = datetime.strptime(input_date, "%m-%d-%Y")
    date_for_url = dt.strftime("%m-%d-%Y")
    folder_date = dt.strftime("%Y%m%d")
except ValueError:
    print("Invalid date format. Use MM-DD-YYYY.")
    sys.exit(1)

# === DB: Connect & resolve logging context ===
conn, cursor = get_db_cursor()
TOOL_ID = 26
context = get_task_context_by_tool_id(cursor, TOOL_ID)
fk_task_run = context["fk_task_run"] if context else None

log_message(cursor, fk_task_run, "INFO", f"Started LA Media unfiled scraper for {input_date}")

# === DB: Fetch login credentials (tool id = 26) ===
try:
    cursor.execute("""
        SELECT [login_url], [username], [pass]
        FROM [docketwatch].[dbo].[tools]
        WHERE id = ?
    """, (TOOL_ID,))
    row = cursor.fetchone()
    if not row:
        log_message(cursor, fk_task_run, "ERROR", "Tool config not found for Tool ID 26.")
        sys.exit(1)
    login_url, username, password = row
except Exception as e:
    log_message(cursor, fk_task_run, "ERROR", f"DB query failed: {e}")
    sys.exit(1)

# === Setup ChromeDriver ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# === Step 1: Log into media.lacourt.org ===
try:
    log_message(cursor, fk_task_run, "INFO", f"Navigating to login URL: {login_url}")
    driver.get(login_url)
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()
    time.sleep(5)
    if "signin-oidc" in driver.current_url or "media.lacourt.org" in driver.current_url:
        log_message(cursor, fk_task_run, "INFO", "Login successful.")
    else:
        log_message(cursor, fk_task_run, "ERROR", f"Login failed. Current URL: {driver.current_url}")
        driver.quit()
        sys.exit(1)
    cookies = driver.get_cookies()
    cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
    driver.quit()
except Exception as e:
    log_message(cursor, fk_task_run, "ERROR", f"Login failed: {e}")
    driver.quit()
    sys.exit(1)

# === Step 2: Call GetRecentFilings for provided date ===
api_url = f"https://media.lacourt.org/api/AzureApi/GetRecentFilings/{date_for_url}/{date_for_url}"
headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}
log_message(cursor, fk_task_run, "INFO", f"Requesting API: {api_url}")

try:
    response = requests.get(api_url, headers=headers)
    data = response.json()
    filings = data.get("ResultList", [])

    new_case_count = 0

    for filing in filings:
        lead_doc = filing.get("LeadDocument", {})
        court_case_number = lead_doc.get("LeadDocumentID")
        case_type = lead_doc.get("DocumentDescriptionText", "").strip() or "Unknown"

        # Clean party names
        plaintiff = filing.get("PlaintiffName", "") or ""
        defendant = filing.get("DefendantName", "") or ""

        removals = [
            ", An Individual (Plaintiff)", "(Defendant)+", "(Plaintiff)+",
            "(Defendant)", "(Plaintiff)", "(Petitioner)", "(Respondent)", "+"
        ]
        for term in removals:
            plaintiff = plaintiff.replace(term, "")
            defendant = defendant.replace(term, "")
        plaintiff = re.sub(r'\s+', ' ', plaintiff).strip()
        defendant = re.sub(r'\s+', ' ', defendant).strip()

        case_name = f"{plaintiff} VS {defendant}" if defendant else plaintiff
        case_number = "Unfiled"

        # Check if case exists (status <> 'Removed') and get fk_case if it does
        cursor.execute("""
            SELECT id FROM docketwatch.dbo.cases
            WHERE case_number = ? AND case_name = ? 
        """, (case_number, case_name))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.cases (
                    courtCaseNumber, case_number, case_name, status, case_type, fk_tool
                )
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(court_case_number), case_number, case_name, "Review", case_type, TOOL_ID))
            fk_case = cursor.fetchone()[0]
            conn.commit()
            new_case_count += 1
            log_message(cursor, fk_task_run, "ALERT", f"Inserted: {case_name} (LeadDocID: {court_case_number})", fk_case=fk_case)
        else:
            fk_case = row[0]
            log_message(cursor, fk_task_run, "INFO", f"Case already exists: {case_name}", fk_case=fk_case)

    log_message(cursor, fk_task_run, "INFO", f"Finished: {new_case_count} new cases inserted for {input_date}")

except Exception as e:
    log_message(cursor, fk_task_run, "ERROR", f"Failed to process or insert recent filings: {e}")

# === Run docketwatch_process.py (same directory) ===
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    process_script = os.path.join(current_dir, "docketwatch_process.py")
    log_message(cursor, fk_task_run, "INFO", f"Running post-processing: {process_script}")

    result = subprocess.run(["python", process_script], capture_output=True, text=True)
    if result.stdout:
        log_message(cursor, fk_task_run, "INFO", f"Process stdout: {result.stdout[:500]}")
    if result.stderr:
        log_message(cursor, fk_task_run, "WARNING", f"Process stderr: {result.stderr[:500]}")

except Exception as e:
    log_message(cursor, fk_task_run, "ERROR", f"Failed to run docketwatch_process.py: {e}")

log_message(cursor, fk_task_run, "INFO", f"Script completed for {input_date}")

# Cleanup DB connections (do this last!)
cursor.close()
conn.close()
