import os
import json
import pyodbc
import time
import requests
import logging
import markdown2
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scraper_base import log_message, mark_case_not_found, mark_case_found

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

log_message(cursor, fk_task_run, "INFO", "=== LaCourt API Auth + Scraper Started ===")

# === Setup ChromeDriver ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)
log_message(cursor, fk_task_run, "INFO", "ChromeDriver initialized.")

# === Fetch credentials and URLs from DB (tool id = 12) ===
cursor.execute("""
    SELECT [login_url], [username], [pass], [search_url]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = 12
""")
login_row = cursor.fetchone()
if not login_row:
    log_message(cursor, fk_task_run, "ERROR", "No credentials found for tool id 12.")
    driver.quit()
    conn.close()
    exit()
login_url, username, password, _ = login_row
log_message(cursor, fk_task_run, "INFO", "Fetched login credentials from database.")

# === Step 1: Log into the page (robust + validated) ===
try:
    log_message(cursor, fk_task_run, "INFO", "Navigating to login page...")
    driver.get(login_url)
    wait = WebDriverWait(driver, 20)
    log_message(cursor, fk_task_run, "INFO", "Waiting for login form to appear...")
    wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()
    log_message(cursor, fk_task_run, "INFO", "Login submitted, waiting for OpenID redirect...")
    time.sleep(5)
    if "signin-oidc" in driver.current_url or "media.lacourt.org" in driver.current_url:
        log_message(cursor, fk_task_run, "INFO", "Login successful.")
    else:
        log_message(cursor, fk_task_run, "ERROR", f"Login may have failed. Current URL: {driver.current_url}")
        driver.quit()
        exit()
except Exception as e:
    log_message(cursor, fk_task_run, "ERROR", f"Login failed: {str(e)}")
    driver.quit()
    exit()

# === Step 2: Extract .AspNetCore.Cookies ===
cookies = driver.get_cookies()
cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
driver.quit()
log_message(cursor, fk_task_run, "INFO", "Extracted auth cookie from session.")

# === Fetch Gemini Key ===
cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
gemini_key_row = cursor.fetchone()
gemini_key = gemini_key_row[0] if gemini_key_row else None

# === Fetch cases records ===
cursor.execute("""
    SELECT TOP 100 [case_number], [map_id], id as [fk_case], [case_name], [summarize]
    FROM [docketwatch].[dbo].[cases]
    WHERE fk_tool = 12 and status = 'Tracked' and map_id is not null
    ORDER BY last_updated;
""")
tool_cases = cursor.fetchall()
if not tool_cases:
    log_message(cursor, fk_task_run, "INFO", "No tracked cases found to process.")

def generate_and_save_map_summary(cursor, conn, fk_case, case_number, case_name, map_case_data, gemini_key):
    prompt = f"""
You are a legal analyst summarizing a civil case for an internal newsroom research tool.

Summarize the key details of this court case based solely on the following JSON data from the court's API.

Include:
- Case number, case title, case type, filing date, courthouse, judicial officer.
- Petitioner(s) and respondent(s).
- Key documents filed (title + date).
- Any past proceedings and their results.
- Register of actions (chronological summary).
- Case disposition and current status.
- If relevant, include why this case might interest a news outlet.

Use plain English. Be concise but informative. Max 500 words.

--- START JSON ---
{json.dumps(map_case_data, indent=2)}
--- END JSON ---
"""
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={gemini_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1200}
            }),
            timeout=90
        )
        response.raise_for_status()
        gemini_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        html_version = BeautifulSoup(markdown2.markdown(gemini_text), "html.parser").prettify()
        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET summarize = ?, summarize_html = ?, ai_processed_at = ?
            WHERE id = ?
        """, (gemini_text[:4000], html_version[:8000], datetime.now(), fk_case))
        conn.commit()
        log_message(cursor, fk_task_run, "INFO", f"Summary saved for case {case_number}", fk_case=fk_case)
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Gemini summary failed: {e}", fk_case=fk_case)

for case_number, map_id, fk_case, case_name, summarize in tool_cases:
    headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}
    api_url = f"https://media.lacourt.org/api/AzureApi/GetCaseDetail/{map_id}"
    log_message(cursor, fk_task_run, "INFO", f"Making API request to {api_url}", fk_case=fk_case)
    response = requests.get(api_url, headers=headers)

    try:
        data = response.json()
        log_message(cursor, fk_task_run, "INFO", f"Parsed JSON response for case {case_number}.", fk_case=fk_case)

        # RegisterOfActions
        actions = data.get("ResultList", [])[0].get("NonCriminalCaseInformation", {}).get("RegisterOfActions", [])
        log_message(cursor, fk_task_run, "INFO", f"Found {len(actions)} events for case {case_number}.", fk_case=fk_case)
        mark_case_found(cursor, fk_case)

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
            if cursor.fetchone()[0] > 0:
                continue
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_events (event_date, event_description, additional_information, fk_cases)
                VALUES (?, ?, ?, ?)
            """, (event_date, event_description, additional_information, fk_case))
            conn.commit()

        # Hearings
        hearings = data["ResultList"][0]["NonCriminalCaseInformation"].get("FutureProceedings", [])
        for h in hearings:
            date_str = h.get("ProceedingDateString", "").strip()
            time_str = h.get("ProceedingTime", "").strip()
            ampm = h.get("AMPM", "AM").strip()
            event = h.get("Event", "").strip()
            result = h.get("Result", "").strip()
            room = h.get("ProceedingRoom", "").strip()
            judge = h.get("Judge", "").strip()
            if not date_str or not time_str or not event:
                continue
            try:
                dt_str = f"{date_str} {time_str} {ampm}"
                hearing_datetime = datetime.strptime(dt_str, "%m/%d/%Y %I:%M %p")
            except:
                continue
            cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.hearings WHERE fk_case = ? AND hearing_datetime = ?", (fk_case, hearing_datetime))
            if cursor.fetchone()[0] > 0:
                continue
            cursor.execute("""
                INSERT INTO docketwatch.dbo.hearings (fk_case, hearing_type, hearing_datetime, result, hearing_room, judge)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fk_case, event, hearing_datetime, result, room, judge))
            conn.commit()

        # Case Update
        header_info = data["ResultList"][0]["HeaderInformation"]
        case_info = data["ResultList"][0]["NonCriminalCaseInformation"]["CaseInformation"]
        def get_header_value(key_name):
            for item in header_info:
                if item["Key"] == key_name:
                    return item["Value"]
            return None
        case_number_updated = get_header_value("Case Number")
        case_title = get_header_value("Case Title")
        case_type_note = get_header_value("Case Type")
        filing_courthouse = get_header_value("Filing Courthouse")
        cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_name = ?", filing_courthouse)
        court_row = cursor.fetchone()
        court_code = court_row[0] if court_row else None
        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET case_name = ?, fk_court = ?, notes = ?, case_type = ?, case_url = ISNULL(case_url, ?), last_updated = GETDATE()
            WHERE id = ?
        """, (
            case_title,
            court_code,
            case_type_note,
            case_info.get("LitigationTypeObject", {}).get("Description", ""),
            f"https://www.lacourt.org/casesummary/ui/casesummary.aspx?casetype=familylaw&casenumber={case_number_updated}",
            fk_case
        ))
        conn.commit()

        # Generate Gemini summary only if not already present
        if not summarize:
            generate_and_save_map_summary(cursor, conn, fk_case, case_number, case_name, data, gemini_key)

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Failed to parse/process JSON for case {case_number}: {str(e)}")
        mark_case_not_found(cursor, fk_case, fk_task_run)
        continue

cursor.close()
conn.close()
log_message(cursor, fk_task_run, "INFO", "Database connection closed.")
log_message(cursor, fk_task_run, "INFO", "=== LaCourt API Scraper Completed ===")
