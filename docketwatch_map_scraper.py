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
from scraper_base import log_message
from scraper_base import mark_case_not_found, mark_case_found
from error_notification_system import create_error_notifier

# === GET SCRIPT NAME ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# === Initialize error notification system ===
error_notifier = create_error_notifier(script_filename)

# === DATABASE CONNECTION & TASK RUN ===
try:
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

except Exception as e:
    error_msg = f"Database connection failed: {e}"
    print(error_msg)
    error_notifier.log_database_error(error_msg)
    raise

# === LOGGING SETUP ===
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

log_message(cursor, fk_task_run, "INFO", "=== LaCourt API Auth + Scraper Started ===")

# Wrap entire script in error handling
try:
    # === Setup ChromeDriver ===
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMEDRIVER_PATH)

    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        log_message(cursor, fk_task_run, "INFO", "ChromeDriver initialized.")

        # === Fetch credentials and URLs from DB (tool id = 12) ===
        try:
            cursor.execute("""
                SELECT [login_url], [username], [pass], [search_url]
                FROM [docketwatch].[dbo].[tools]
                WHERE id = 12
            """)
            login_row = cursor.fetchone()
            if not login_row:
                error_msg = "No credentials found for tool id 12."
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_critical_error(error_msg, fk_task_run=fk_task_run)
                conn.close()
                exit()
            login_url, username, password, _ = login_row
            log_message(cursor, fk_task_run, "INFO", "Fetched login credentials from database.")
        except Exception as e:
            error_msg = f"Failed to fetch credentials from database: {e}"
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
            conn.close()
            exit()

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
                error_msg = f"Login may have failed. Current URL: {driver.current_url}"
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error("Chrome Login Failed", error_msg, fk_task_run=fk_task_run)
                conn.close()
                exit()

        except Exception as e:
            error_msg = f"Login failed: {str(e)}"
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            error_notifier.log_chrome_error(error_msg, fk_task_run=fk_task_run)
            conn.close()
            exit()

        # === Step 2: Extract .AspNetCore.Cookies ===
        cookies = driver.get_cookies()
        cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
        auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
        log_message(cursor, fk_task_run, "INFO", "Extracted auth cookie from session.")

    finally:
        # === Ensure ChromeDriver is always properly closed ===
        if driver:
            try:
                driver.quit()
                log_message(cursor, fk_task_run, "INFO", "ChromeDriver properly closed.")
            except Exception as cleanup_error:
                error_msg = f"Error during driver cleanup: {str(cleanup_error)}"
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_chrome_error(error_msg, fk_task_run=fk_task_run)

    # === Fetch cases records ===
    try:
        cursor.execute("""
            SELECT  [case_number], [map_id], id as [fk_case], [case_name]
            FROM [docketwatch].[dbo].[cases]
            WHERE fk_tool = 12 and status = 'Tracked' and map_id is not null
            ORDER BY last_updated;
        """)
        tool_cases = cursor.fetchall()
        if not tool_cases:
            log_message(cursor, fk_task_run, "INFO", "No tracked cases found to process.")
    except Exception as e:
        error_msg = f"Failed to fetch cases from database: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
        cursor.close()
        conn.close()
        exit()

    try:
        session = requests.Session()
        session.headers.update({"cookie": f".AspNetCore.Cookies={auth_cookie}"})
    except Exception as e:
        error_msg = f"Failed to create requests session with auth cookie: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("Session Creation Failed", error_msg, fk_task_run=fk_task_run)
        cursor.close()
        conn.close()
        exit()

    for case_number, map_id, fk_case, case_name in tool_cases:
        try:
            api_url = f"https://media.lacourt.org/api/AzureApi/GetCaseDetail/{map_id}"
            response = session.get(api_url)
            
            # Check if API request was successful
            if response.status_code != 200:
                error_msg = f"API request failed for case {case_number} (map_id: {map_id}): HTTP {response.status_code}"
                log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                error_notifier.log_error("API Request Failed", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}")
                mark_case_not_found(cursor, fk_case, fk_task_run)
                continue

            try:
                data = response.json()
                log_message(cursor, fk_task_run, "INFO", f"Parsed JSON response for case {case_number}.", fk_case=fk_case)

                # NEW: Save raw JSON into case_json column
                try:
                    cursor.execute("""
                        UPDATE docketwatch.dbo.cases
                        SET case_json = ?
                        WHERE id = ?
                    """, (json.dumps(data), fk_case))
                    conn.commit()
                except Exception as json_save_error:
                    error_msg = f"Failed to save JSON data for case {case_number}: {json_save_error}"
                    log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                    error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
                    # Continue processing even if JSON save fails

                # --- Insert RegisterOfActions (case events) ---
                try:
                    result_list = data.get("ResultList", [])
                    if not result_list:
                        log_message(cursor, fk_task_run, "WARNING", f"No ResultList found in API response for case {case_number}.", fk_case=fk_case)
                        mark_case_not_found(cursor, fk_case, fk_task_run)
                        continue
                    
                    first_result = result_list[0]
                    non_criminal_info = first_result.get("NonCriminalCaseInformation", {})
                    if not non_criminal_info:
                        log_message(cursor, fk_task_run, "WARNING", f"No NonCriminalCaseInformation found for case {case_number}.", fk_case=fk_case)
                        mark_case_not_found(cursor, fk_case, fk_task_run)
                        continue
                    
                    actions = non_criminal_info.get("RegisterOfActions", [])
                    log_message(cursor, fk_task_run, "INFO", f"Found {len(actions)} events for case {case_number}.", fk_case=fk_case)
                    mark_case_found(cursor, fk_case)

                    inserted = 0
                    for action in actions:
                        try:
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
                            inserted += 1
                            log_message(cursor, fk_task_run, "ALERT", f"Inserted event for {case_name}: {event_description} on {event_date}", fk_case=fk_case)
                        except Exception as event_insert_error:
                            error_msg = f"Failed to insert event for case {case_number}: {event_insert_error}"
                            log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                            error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
                            continue  # Continue with next event

                except Exception as actions_error:
                    error_msg = f"Failed to process events for case {case_number}: {actions_error}"
                    log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                    error_notifier.log_error("Event Processing Failed", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}")

                # Skipping: Future hearings, case header updates, etc. — retained in original.

            except json.JSONDecodeError as json_error:
                error_msg = f"Failed to parse JSON response for case {case_number}: {json_error}"
                log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                error_notifier.log_error("JSON Parse Error", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}, API URL: {api_url}")
                mark_case_not_found(cursor, fk_case, fk_task_run)
                continue
            except Exception as e:
                error_msg = f"Failed to parse/process JSON for case {case_number}: {str(e)}"
                log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                error_notifier.log_error("Case Processing Error", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}")
                mark_case_not_found(cursor, fk_case, fk_task_run)
                continue
        except Exception as case_error:
            error_msg = f"Unexpected error processing case {case_number}: {case_error}"
            log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
            error_notifier.log_error("Case Processing Exception", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}")
            mark_case_not_found(cursor, fk_case, fk_task_run)
            continue

    # Cleanup
    try:
        cursor.close()
        conn.close()
        log_message(cursor, fk_task_run, "INFO", "Database connection closed.")
        log_message(cursor, fk_task_run, "INFO", "=== LaCourt API Scraper Completed ===")
    except Exception as cleanup_error:
        error_msg = f"Error during database cleanup: {cleanup_error}"
        print(error_msg)  # Use print since cursor might be closed
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)

except Exception as e:
    # Handle any unhandled exceptions at the top level
    error_msg = f"Critical script failure: {str(e)}"
    print(error_msg)
    try:
        log_message(cursor, fk_task_run, "ERROR", error_msg)
    except:
        pass  # Don't fail if logging fails
    
    error_notifier.log_critical_error(
        error_msg, 
        fk_task_run=fk_task_run,
        additional_context="Script failed at top level - check logs for details"
    )
    raise
