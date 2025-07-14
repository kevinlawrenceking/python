import time
import pyodbc
import os
import sys
import logging
import psutil
import random
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

FROM_EMAIL = "it@tmz.com"
TO_EMAIL = "Jennifer.Delgado@tmz.com","Kevin.King@tmz.com","Marlee.Goodman@tmz.com","Priscilla.Hwang@tmz.com","Shirley.Troche@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

def send_docket_email(case_name, case_url, event_no, cleaned_docket_text):
    subject = f"DocketWatch Alert: {case_name} – New Docket Discovered"

    body = f"""
    <html>
    <body>
        A new docket has been detected for case:<br>
        <a href="{case_url}">{case_name}</a><br><br>
        <strong>Docket No:</strong> {event_no}<br>
        <strong>Description:</strong><br>
        <p>{cleaned_docket_text}</p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
        log_message("ALERT", f"Email sent for new docket in case {case_name}")
    except Exception as e:
        log_message("ERROR", f"Failed to send email for case {case_name}: {e}")




# Configure Logging
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_pacer_scraper.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Extract script filename without extension
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# Database Connection
try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    cursor = conn.cursor()
    logging.info("Database Connection Established")
except Exception as e:
    logging.error(f"Database Connection Failed: {str(e)}")
    sys.exit(1)

# Fetch Task Run ID
cursor.execute("""
    SELECT TOP 1 r.id as fk_task_run 
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
    WHERE s.filename = ? 
    ORDER BY r.id DESC
""", (script_filename,))
task_run = cursor.fetchone()
fk_task_run = task_run[0] if task_run else None

# Logging Function
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

log_message("INFO", "=== PACER Scraper Started ===")

# Prevent Multiple Script Instances
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_pacer_scraper.lock"
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

# Get PACER Credentials
try:
    cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
    row = cursor.fetchone()
    if not row:
        log_message("ERROR", "PACER credentials not found in the database.")
        sys.exit(1)
    USERNAME, PASSWORD, LOGIN_URL = row
    log_message("INFO", "PACER credentials retrieved successfully")
except Exception as e:
    log_message("ERROR", f"Error retrieving PACER credentials: {str(e)}")
    sys.exit(1)

# Setup Selenium WebDriver
try:
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    log_message("INFO", "ChromeDriver Initialized Successfully")
except Exception as e:
    log_message("ERROR", f"ChromeDriver Initialization Failed: {str(e)}")
    sys.exit(1)

def human_pause(min_time=1, max_time=3):
    time.sleep(random.uniform(min_time, max_time))

def clean_text(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text).replace("'", "''").replace("\n", " ").replace("\r", " ")
    return text[:4000]

try:
    # Step 1: Log Into PACER
    driver.get(LOGIN_URL)
    human_pause(2, 4)
    driver.find_element(By.NAME, "loginForm:loginName").send_keys(USERNAME)
    human_pause(1, 2)
    driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
    human_pause(2, 3)
    driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
    human_pause(3, 5)
    log_message("INFO", "PACER login successful.")

    # Step 2: Query Tracked Cases
    cursor.execute("""
        SELECT id, id as fk_case, case_url, case_name, case_number
        FROM dbo.cases 
        WHERE is_tracked = 1 AND fk_tool = 2 AND case_url IS NOT NULL
    """)
    cases = cursor.fetchall()
    if not cases:
        log_message("WARNING", "No tracked cases found for PACER. Exiting...")
        driver.quit()
        conn.close()
        os.remove(LOCK_FILE)
        sys.exit()

    for case in cases:
        case_id, fk_case, case_url, case_name, case_number = case
        log_id = log_message("INFO", f"Reviewing case: {case_name}")
        cursor.execute("""
            UPDATE dbo.cases SET fk_task_run_log = ? WHERE id = ?
        """, (log_id, case_id))
        conn.commit()

        driver.get(case_url)
        human_pause(3, 5)
        driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report").click()
        human_pause(3, 5)
        for checkbox_name in ["list_of_parties_and_counsel", "terminated_parties"]:
            checkbox = driver.find_element(By.NAME, checkbox_name)
            if checkbox.is_selected():
                checkbox.click()
            human_pause(1, 2)
        Select(driver.find_element(By.NAME, "sort1")).select_by_visible_text("Most recent date first")
        human_pause(1, 2)
        driver.find_element(By.NAME, "button1").click()
        human_pause(3, 5)

        cursor.execute("SELECT COUNT(*) FROM dbo.case_events WHERE fk_cases = ?", (fk_case,))
        existing_dockets = cursor.fetchone()[0]
        log_message("INFO", f"{existing_dockets} existing dockets for case {case_name}")

        docket_rows = driver.find_elements(By.XPATH, "//table[@border='1']/tbody/tr")
        for row in docket_rows[1:]:
            columns = row.find_elements(By.TAG_NAME, "td")
            if len(columns) < 3:
                continue
            event_date, docket_number_text, docket_text = columns[0].text.strip(), columns[1].text.strip(), columns[2].text.strip()
            event_no = int(docket_number_text) if docket_number_text.isdigit() else 0
            cleaned_docket_text = clean_text(docket_text)
            cursor.execute("""
                SELECT COUNT(*) FROM dbo.case_events WHERE event_date = ? AND LEFT(event_description, 100) = ? AND fk_cases = ?
            """, (event_date, cleaned_docket_text[:100], fk_case))
            exists = cursor.fetchone()[0]

            if not exists:
                log_id = log_message("ALERT", f"New docket discovered! Docket added to case {case_name}")
                
                cursor.execute("""
                    INSERT INTO dbo.case_events (
                        event_date, event_no, event_description, fk_cases, status, fk_task_run_log
                    ) VALUES (?, ?, ?, ?, 'New', ?)
                """, (event_date, event_no, cleaned_docket_text, fk_case, log_id))
                conn.commit()
                
                # Send Email Notification
                send_docket_email(case_name, case_url, event_no, cleaned_docket_text)
            else:
                log_message("INFO", f"Docket number {event_no} already exists for case {case_name}")

except Exception as e:
    log_message("ERROR", f"Script Failed: {str(e)}")
finally:
    cursor.close()
    conn.close()
    driver.quit()
    os.remove(LOCK_FILE)
    log_message("INFO", "PACER Scraper Completed Successfully")
