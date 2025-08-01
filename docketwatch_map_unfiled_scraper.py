import subprocess
import re
import os
import sys
import time
import json
import glob
import tempfile
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
from scraper_base import log_message, get_task_context_by_tool_id, get_db_cursor, setup_logging, insert_documents_for_event
from error_notification_system import create_error_notifier

# Setup Error Notification System
script_name = os.path.splitext(os.path.basename(__file__))[0]
error_notifier = create_error_notifier(script_name)

def check_disk_space():
    """
    Check available disk space in temp directory and warn if running low.
    """
    try:
        import shutil
        temp_dir = tempfile.gettempdir()
        total, used, free = shutil.disk_usage(temp_dir)
        
        # Convert to GB for easier reading
        free_gb = free / (1024**3)
        total_gb = total / (1024**3)
        used_percent = (used / total) * 100
        
        print(f"Disk space check - Free: {free_gb:.2f} GB, Used: {used_percent:.1f}% of {total_gb:.2f} GB")
        
        # Warn if less than 2 GB free or more than 95% used
        if free_gb < 2.0 or used_percent > 95:
            print(f"WARNING: Low disk space detected! Free: {free_gb:.2f} GB, Used: {used_percent:.1f}%")
            return False
        return True
        
    except Exception as e:
        print(f"Error checking disk space: {e}")
        return True  # Assume OK if we can't check

def cleanup_temp_chrome_profiles():
    """
    Clean up any orphaned Chrome profile directories that might be left behind.
    This helps prevent disk space issues.
    """
    try:
        temp_dir = tempfile.gettempdir()
        pattern = os.path.join(temp_dir, "chrome_profile_*")
        old_profiles = glob.glob(pattern)
        
        if old_profiles:
            print(f"Found {len(old_profiles)} old Chrome profile directories to clean up")
            for profile_dir in old_profiles:
                try:
                    # Only remove directories older than 1 hour to avoid conflicts
                    if os.path.exists(profile_dir):
                        dir_age = time.time() - os.path.getctime(profile_dir)
                        if dir_age > 3600:  # 1 hour in seconds
                            import shutil
                            shutil.rmtree(profile_dir, ignore_errors=True)
                            print(f"Cleaned up old Chrome profile: {profile_dir}")
                except Exception as e:
                    print(f"Could not clean up profile {profile_dir}: {e}")
        
        # Also clean up any puppeteer_dev_chrome_profile directories
        puppeteer_pattern = os.path.join(temp_dir, "puppeteer_dev_chrome_profile-*")
        old_puppeteer_profiles = glob.glob(puppeteer_pattern)
        
        if old_puppeteer_profiles:
            print(f"Found {len(old_puppeteer_profiles)} old Puppeteer profile directories to clean up")
            for profile_dir in old_puppeteer_profiles:
                try:
                    if os.path.exists(profile_dir):
                        dir_age = time.time() - os.path.getctime(profile_dir)
                        if dir_age > 3600:  # 1 hour in seconds
                            import shutil
                            shutil.rmtree(profile_dir, ignore_errors=True)
                            print(f"Cleaned up old Puppeteer profile: {profile_dir}")
                except Exception as e:
                    print(f"Could not clean up Puppeteer profile {profile_dir}: {e}")
                    
    except Exception as e:
        print(f"Error during temp directory cleanup: {e}")

def download_pdf_for_case(court_case_number, fk_case, auth_cookie, cursor, fk_task_run, max_retries=2):
    """
    Download PDF for a specific case using the existing download_map_filing.js logic.
    Returns True if PDF was successfully downloaded and document record created.
    """
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                log_message(cursor, fk_task_run, "INFO", f"Retry attempt {attempt} for case {fk_case}, court number: {court_case_number}")
            else:
                log_message(cursor, fk_task_run, "INFO", f"Starting PDF download for case {fk_case}, court number: {court_case_number}")
            
            # For unfiled cases, generate filename
            filename_for_url = f"E{court_case_number}"  # No extension for URL
            filename_for_file = f"E{court_case_number}.pdf"  # With extension for file
            
            # Prepare environment variables for Node.js script
            env = {
                "FILE_NAME": filename_for_url,
                "KEY": "",  # Empty for unfiled cases
                "END": "",  # Empty for unfiled cases
                "COOKIE": auth_cookie,
                "COURT_CASE_NUMBER": str(court_case_number),
                "FK_CASE": str(fk_case),
                "IS_UNFILED": "true",
            }
            
            log_message(cursor, fk_task_run, "INFO", f"Launching PDF download for {filename_for_file}")
            
            # Run the Node.js PDF download script
            result = subprocess.run(
                ["node", "download_map_filing.js"],
                env={**env, **dict(os.environ)},
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                timeout=900  # 15 minute timeout per PDF (increased from 5 minutes)
            )
            
            if result.returncode != 0:
                error_msg = f"PDF download failed for case {fk_case}, court number: {court_case_number} (attempt {attempt + 1}): {result.stderr}"
                if attempt < max_retries:
                    log_message(cursor, fk_task_run, "WARNING", error_msg)
                    time.sleep(30)  # Wait 30 seconds before retry
                    continue
                else:
                    log_message(cursor, fk_task_run, "ERROR", error_msg)
                    error_notifier.log_error(
                        "PDF Download Failed",
                        error_msg,
                        fk_task_run=fk_task_run,
                        additional_context=f"Case: {fk_case}, Court Number: {court_case_number}, Return Code: {result.returncode}"
                    )
                    return False
            
            # Check if PDF was actually created
            expected_pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{fk_case}\\{filename_for_file}"
            
            if os.path.exists(expected_pdf_path):
                log_message(cursor, fk_task_run, "SUCCESS", f"PDF successfully saved: {expected_pdf_path}")
                
                # Create case_event for this PDF download
                try:
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.case_events (
                            fk_cases, event_date, event_description, created_at, emailed
                        )
                        OUTPUT INSERTED.id
                        VALUES (?, GETDATE(), 'MAP Document Download', GETDATE(), 1)
                    """, (fk_case,))
                    case_event_id = cursor.fetchone()[0]
                    
                    # Create document record
                    docs_created = insert_documents_for_event(cursor, case_event_id, tool_id=26)
                    if docs_created > 0:
                        log_message(cursor, fk_task_run, "SUCCESS", f"Created {docs_created} document record(s) for case {fk_case}")
                        return True
                    else:
                        log_message(cursor, fk_task_run, "WARNING", f"PDF downloaded but no document records created for case {fk_case}")
                        error_notifier.log_error(
                            "Document Record Creation Failed",
                            f"PDF downloaded but no document records created for case {fk_case}",
                            fk_task_run=fk_task_run,
                            additional_context=f"Court Number: {court_case_number}"
                        )
                        return False
                        
                except Exception as db_error:
                    error_msg = f"Database error creating case event/document for case {fk_case}: {db_error}"
                    log_message(cursor, fk_task_run, "ERROR", error_msg)
                    error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
                    return False
                    
            else:
                error_msg = f"PDF not found at expected location: {expected_pdf_path}"
                if attempt < max_retries:
                    log_message(cursor, fk_task_run, "WARNING", error_msg + f" (attempt {attempt + 1})")
                    time.sleep(30)  # Wait 30 seconds before retry
                    continue
                else:
                    log_message(cursor, fk_task_run, "ERROR", error_msg)
                    error_notifier.log_error(
                        "PDF File Not Found",
                        error_msg,
                        fk_task_run=fk_task_run,
                        additional_context=f"Case: {fk_case}, Court Number: {court_case_number}"
                    )
                    return False
                
        except subprocess.TimeoutExpired:
            error_msg = f"PDF download timed out for case {fk_case}, court number: {court_case_number}"
            if attempt < max_retries:
                log_message(cursor, fk_task_run, "WARNING", error_msg + f" (attempt {attempt + 1})")
                time.sleep(60)  # Wait 60 seconds before retry for timeout
                continue
            else:
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error(
                    "PDF Download Timeout",
                    error_msg,
                    fk_task_run=fk_task_run,
                    additional_context="Node.js script exceeded 5-minute timeout"
                )
                return False
        except Exception as e:
            error_msg = f"Exception during PDF download for case {fk_case}, court number: {court_case_number}: {e}"
            if attempt < max_retries:
                log_message(cursor, fk_task_run, "WARNING", error_msg + f" (attempt {attempt + 1})")
                time.sleep(30)  # Wait 30 seconds before retry
                continue
            else:
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error(
                    "PDF Download Exception",
                    error_msg,
                    fk_task_run=fk_task_run,
                    additional_context=f"Case: {fk_case}, Court Number: {court_case_number}"
                )
                return False
    
    return False  # Should never reach here, but just in case

# === Set up logging file path ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]
log_path = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
setup_logging(log_path)

# === Clean up any orphaned Chrome profiles from previous runs ===
cleanup_temp_chrome_profiles()

# === Check available disk space ===
disk_ok = check_disk_space()

# === Get date param from command line ===
if len(sys.argv) < 2:
    error_msg = "Usage: python docketwatch_map_unfiled_scraper.py MM-DD-YYYY"
    print(error_msg)
    error_notifier.log_error("Usage Error", error_msg, severity="WARNING", send_email=False)
    sys.exit(1)

# Wrap the entire script in error handling
try:

    input_date = sys.argv[1]
    try:
        dt = datetime.strptime(input_date, "%m-%d-%Y")
        date_for_url = dt.strftime("%m-%d-%Y")
        folder_date = dt.strftime("%Y%m%d")
    except ValueError:
        error_msg = "Invalid date format. Use MM-DD-YYYY."
        print(error_msg)
        error_notifier.log_error("Date Format Error", error_msg, severity="WARNING", send_email=False)
        sys.exit(1)

    # === DB: Connect & resolve logging context ===
    conn, cursor = get_db_cursor()
    TOOL_ID = 26
    context = get_task_context_by_tool_id(cursor, TOOL_ID)
    fk_task_run = context["fk_task_run"] if context else None

    log_message(cursor, fk_task_run, "INFO", f"Started LA Media unfiled scraper for {input_date}")
    log_message(cursor, fk_task_run, "INFO", "Completed temporary Chrome profile cleanup")

    if not disk_ok:
        log_message(cursor, fk_task_run, "WARNING", "Low disk space detected - this may cause PDF download failures")

    # === DB: Fetch login credentials (tool id = 26) ===
    try:
        cursor.execute("""
            SELECT [login_url], [username], [pass]
            FROM [docketwatch].[dbo].[tools]
            WHERE id = ?
        """, (TOOL_ID,))
        row = cursor.fetchone()
        if not row:
            error_msg = "Tool config not found for Tool ID 26."
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
            sys.exit(1)
        login_url, username, password = row
    except Exception as e:
        error_msg = f"DB query failed: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
        sys.exit(1)

    # === Setup ChromeDriver ===
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMEDRIVER_PATH)
    
    driver = None
    try:
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
                error_msg = f"Login failed. Current URL: {driver.current_url}"
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_authentication_error(error_msg, fk_task_run=fk_task_run)
                sys.exit(1)
            cookies = driver.get_cookies()
            cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
            auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
            
            if not auth_cookie:
                error_msg = "Authentication cookie not found after login"
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_authentication_error(error_msg, fk_task_run=fk_task_run)
                sys.exit(1)
            elif len(auth_cookie) < 50:
                log_message(cursor, fk_task_run, "WARNING", f"Authentication cookie seems too short ({len(auth_cookie)} chars): {auth_cookie[:20]}...")
            else:
                log_message(cursor, fk_task_run, "INFO", f"Authentication cookie obtained ({len(auth_cookie)} chars)")
            
        except Exception as e:
            error_msg = f"Login failed: {e}"
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            error_notifier.log_authentication_error(error_msg, fk_task_run=fk_task_run)
            sys.exit(1)
            
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
            try:
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

                # Truncate names to prevent database errors (based on actual database schema)
                max_name_length = 255  # For general name fields
                plaintiff = plaintiff[:max_name_length] if len(plaintiff) > max_name_length else plaintiff
                defendant = defendant[:max_name_length] if len(defendant) > max_name_length else defendant

                case_name = f"{plaintiff} VS {defendant}" if defendant else plaintiff
                
                # Truncate case_name if it's too long (database limit: 500)
                max_case_name_length = 500
                if len(case_name) > max_case_name_length:
                    case_name = case_name[:max_case_name_length - 3] + "..."
                    log_message(cursor, fk_task_run, "WARNING", f"Case name truncated due to length: {case_name}")
                
                case_number = "Unfiled"

                # Truncate case_type (database limit: 200)
                max_case_type_length = 200
                if len(case_type) > max_case_type_length:
                    case_type = case_type[:max_case_type_length]
                    
                # CRITICAL: Truncate courtCaseNumber (database limit: 10 characters!)
                court_case_number_str = str(court_case_number)
                if len(court_case_number_str) > 10:
                    court_case_number_str = court_case_number_str[:10]
                    log_message(cursor, fk_task_run, "WARNING", f"Court case number truncated from {court_case_number} to {court_case_number_str}")

                # Check if case already exists
                cursor.execute("""
                    SELECT id FROM docketwatch.dbo.cases
                    WHERE case_number = ? AND case_name = ? 
                """, (case_number, case_name))
                row = cursor.fetchone()
                
                if not row:
                    # Case doesn't exist - we need to create it and download PDF
                    log_message(cursor, fk_task_run, "INFO", f"New case detected: {case_name} (LeadDocID: {court_case_number})")
                    
                    # Log field lengths for debugging
                    log_message(cursor, fk_task_run, "DEBUG", f"Field lengths - Court#: {len(court_case_number_str)}, CaseName: {len(case_name)}, CaseType: {len(case_type)}")
                    
                    # Insert the case first (but don't commit yet)
                    try:
                        cursor.execute("""
                            INSERT INTO docketwatch.dbo.cases (
                                courtCaseNumber, case_number, case_name, status, case_type, fk_tool
                            )
                            OUTPUT INSERTED.id
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (court_case_number_str, case_number, case_name, "Review", case_type, TOOL_ID))
                        fk_case = cursor.fetchone()[0]
                    except Exception as db_error:
                        error_msg = f"Database insertion failed for case: {case_name[:100]}... Error: {db_error}"
                        log_message(cursor, fk_task_run, "ERROR", error_msg)
                        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
                        continue  # Skip this case and continue with next
                    
                    # Attempt to download PDF for this case (use original court_case_number for PDF naming)
                    pdf_success = download_pdf_for_case(court_case_number, fk_case, auth_cookie, cursor, fk_task_run)
                    
                    if pdf_success:
                        # PDF downloaded successfully - commit the case and all related records
                        conn.commit()
                        new_case_count += 1
                        log_message(cursor, fk_task_run, "ALERT", f"Successfully inserted case with PDF: {case_name} (LeadDocID: {court_case_number})", fk_case=fk_case)
                    else:
                        # PDF download failed - rollback the case insertion
                        conn.rollback()
                        log_message(cursor, fk_task_run, "WARNING", f"PDF download failed - case not inserted: {case_name} (LeadDocID: {court_case_number})")
                else:
                    fk_case = row[0]
                    log_message(cursor, fk_task_run, "INFO", f"Case already exists: {case_name}", fk_case=fk_case)
            
            except Exception as filing_error:
                error_msg = f"Error processing filing: {filing_error}"
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error("Filing Processing Error", error_msg, fk_task_run=fk_task_run)
                # Continue processing other filings

        log_message(cursor, fk_task_run, "INFO", f"Finished: {new_case_count} new cases inserted with PDFs for {input_date}")

    except Exception as e:
        error_msg = f"Failed to process or insert recent filings: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_critical_error(error_msg, fk_task_run=fk_task_run)

    # Note: Post-processing (docketwatch_process.py) is no longer needed as we handle 
    # PDF downloading and document creation inline. Party extraction can be run separately if needed.

    log_message(cursor, fk_task_run, "INFO", f"Script completed for {input_date}")

    # Cleanup DB connections (do this last!)
    cursor.close()
    conn.close()

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
