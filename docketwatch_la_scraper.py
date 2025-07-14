import time
import pyodbc
import re
import os
import sys
import logging
import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from datetime import datetime

# **DATABASE CONNECTION SETTINGS**
DSN = "Docketwatch"

# **GET CURRENT SCRIPT FILENAME (without extension)**
script_filename = os.path.splitext(os.path.basename(__file__))[0]  # e.g., 'docketwatch_la_scraper'

# **CONNECT TO DATABASE**
conn = pyodbc.connect("DSN=" + DSN + ";TrustServerCertificate=yes;")
cursor = conn.cursor()

# **QUERY TO GET LATEST TASK RUN ID**
query = """
    SELECT TOP 1 r.id as fk_task_run 
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
    WHERE s.filename = ? 
    ORDER BY r.id DESC
"""
cursor.execute(query, (script_filename,))

task_run = cursor.fetchone()

# **SET fk_task_run**
fk_task_run = task_run[0] if task_run else None

# **LOGGING CONFIGURATION**
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_la_scraper.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def log_message(log_type, message):
    """Logs to both the log file and the database and returns log ID."""
    logging.info(message)

    if fk_task_run:
        try:
            insert_log_query = """
                INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                OUTPUT INSERTED.id  -- Returns the ID of the newly inserted log entry
                VALUES (?, GETDATE(), ?, ?)
            """
            cursor.execute(insert_log_query, (fk_task_run, log_type, message))
            log_id = cursor.fetchone()[0]  # Fetch the generated log entry ID
            conn.commit()
            return log_id  # Return the log ID
        except pyodbc.Error as e:
            print(f"Database Logging Error: {str(e)}")
            return None  # If logging fails, return None

log_message("INFO", "=== Los Angeles Case Scraper Started ===")

# ** Prevent Multiple Script Instances **
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_la_scraper.lock"

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

if is_another_instance_running():
    log_message("ERROR", "Another instance is already running. Exiting...")
    sys.exit()
else:
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

try:
    # ** Start ChromeDriver **
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    log_message("INFO", "ChromeDriver Initialized Successfully")

    # ** Step 1: Update Existing Cases with NULL fk_court and case_type **
    try:
        update_query = """
            UPDATE c
            SET 
                c.fk_court = cc.fk_court,
                c.case_type = p.practice_name
            FROM docketwatch.dbo.cases c
            LEFT JOIN docketwatch.dbo.case_counter cc 
                ON LEFT(c.case_number, 4) = CAST(cc.yy AS VARCHAR(2)) + cc.fk_court
                AND SUBSTRING(c.case_number, 5, 2) = cc.fk_practice
            LEFT JOIN docketwatch.dbo.courts ct 
                ON cc.fk_court = ct.court_code
            LEFT JOIN docketwatch.dbo.practices p 
                ON cc.fk_practice = p.practice_code
            WHERE c.fk_court IS NULL;
        """
        cursor.execute(update_query)
        conn.commit()
        log_message("INFO", "Updated missing fk_court and case_type values.")
    except Exception as e:
        log_message("ERROR", f"Error updating fk_court and case_type: {str(e)}")

    # ** Query ALL Court/Practice Pairs **
    query = """
        SELECT id, yy, fk_court, fk_practice, last_number, last_updated
        FROM docketwatch.dbo.case_counter
        ORDER BY [priority] ASC
    """
    cursor.execute(query)
    case_counters = cursor.fetchall()

    if not case_counters:
        log_message("WARNING", "No records found in case_counter. Exiting...")
        driver.quit()
        sys.exit()

    # ** Process Each Court/Practice in case_counter **
    for case_counter in case_counters:
        counter_id, yy, fk_court, fk_practice, last_number, _ = case_counter
        yy = str(yy)

        log_message("INFO", f"Searching new cases for {fk_court}-{fk_practice}, starting from {last_number}")

        while True:
            case_number = f"{yy}{fk_court}{fk_practice}{str(last_number).zfill(5)}"
            case_url = f"https://www.lacourt.org/casesummary/ui/index.aspx?casetype=familylaw&casenumber={case_number}"
            driver.get(case_url)
            time.sleep(3)

            page_source = driver.page_source
            if "No match found for case number" in page_source:
                log_message("INFO", f"No match found for {case_number}. Stopping search for this court/practice.")
                break

            try:
                case_number_match = re.search(r"<b>Case Number:</b>&nbsp;&nbsp;</span>(.*?)<br>", page_source, re.DOTALL)
                case_number_text = case_number_match.group(1).strip() if case_number_match else "UNKNOWN"

                case_name_match = re.search(r"<b>Case Number:</b>&nbsp;&nbsp;</span>.*?<br>\s*(.*?)\s*</p>", page_source, re.DOTALL)
                case_name = case_name_match.group(1).strip() if case_name_match else "UNKNOWN"

                case_type_match = re.search(r"<b>Case Type:</b>&nbsp;&nbsp;(.*?)<br>", page_source, re.DOTALL)
                case_type = case_type_match.group(1).replace("</span>", "").strip() if case_type_match else "UNKNOWN"

                # Insert Log Entry and Get Log ID BEFORE Inserting the Case
                log_id = log_message("INFO", f"Inserted case: {case_name}")
                
                if log_id is None:
                    raise Exception(f"Log entry failed for case: {case_name}. Case insertion aborted.")

                # Insert Case with `fk_task_run_log` Instead of `fk_task_run`
                insert_query = """
                    INSERT INTO docketwatch.dbo.cases 
                    (case_url, case_number, case_name, notes, status, owner, fk_court, case_type, fk_task_run_log)
                    SELECT ?, ?, ?, ?, 'Review', 'system', ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM docketwatch.dbo.cases WHERE case_number = ? AND case_name = ?
                    )
                """
                cursor.execute(insert_query, (case_url, case_number_text, case_name, None, fk_court, case_type, log_id, case_number_text, case_name))
                conn.commit()
                last_number += 1

            except Exception as e:
                log_message("ERROR", f"Error extracting details for {case_number}: {str(e)}")
                break

        # ** Update last_number in case_counter table **
        update_query = "UPDATE docketwatch.dbo.case_counter SET last_number = ?, last_updated = GETDATE() WHERE id = ?"
        cursor.execute(update_query, (last_number, counter_id))
        conn.commit()

    # ** Log Completion BEFORE Closing Database Connection **
    log_message("INFO", "Los Angeles Case Scraper Completed Successfully!")

except Exception as e:
    log_message("ERROR", f"Script Failed: {str(e)}")

finally:
    # ** Cleanup and Exit (Now Safe to Close Cursor/Connection) **
    if cursor:
        cursor.close()
    if conn:
        conn.close()
    driver.quit()
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
