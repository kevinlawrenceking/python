# supreme_court_monitor.py
# Monitors Supreme Court RSS JSON feeds for new proceedings and orders

import json
import requests
import pyodbc
import os
import sys
import logging
import psutil
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from scraper_base import log_message

# Email configuration
FROM_EMAIL = "it@tmz.com"
TO_EMAILS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "marlee.chartash@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

# File paths
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\supreme_court_monitor.log"
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\supreme_court_monitor.lock"
DATA_FILE = r"\\10.146.176.84\general\docketwatch\python\data\supreme_court_data.json"

script_filename = os.path.splitext(os.path.basename(__file__))[0]

# Logging setup
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def is_another_instance_running():
    """Check if another instance is already running"""
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

def create_lock_file():
    """Create lock file with current PID"""
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def remove_lock_file():
    """Remove lock file"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass

def load_previous_data():
    """Load previously stored case data"""
    print(f"Loading previous data from: {DATA_FILE}")
    logging.info(f"Loading previous data from: {DATA_FILE}")
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Previous data loaded successfully. Found {len(data)} cases in storage.")
            logging.info(f"Previous data loaded successfully. Found {len(data)} cases in storage.")
            return data
        except Exception as e:
            print(f"ERROR: Error loading previous data: {e}")
            logging.error(f"Error loading previous data: {e}")
    else:
        print("No previous data file found. This is the first run.")
        logging.info("No previous data file found. This is the first run.")
    return {}

def save_current_data(data):
    """Save current case data"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving current data: {e}")

def fetch_supreme_court_data(case_number):
    """Fetch current data from Supreme Court RSS JSON"""
    url = f"https://www.supremecourt.gov/RSS/Cases/JSON/{case_number}.json"
    print(f"Fetching data from: {url}")
    logging.info(f"Fetching data from: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"Successfully fetched JSON data for case {case_number}")
        print(f"Case: {data.get('PetitionerTitle', 'Unknown')} v. {data.get('RespondentTitle', 'Unknown')}")
        print(f"Number of proceedings: {len(data.get('ProceedingsandOrder', []))}")
        
        # Print the JSON data for debugging
        print("=" * 50)
        print("FULL JSON DATA:")
        print(json.dumps(data, indent=2))
        print("=" * 50)
        
        logging.info(f"Successfully fetched data for case {case_number}: {data.get('PetitionerTitle', 'Unknown')} v. {data.get('RespondentTitle', 'Unknown')}")
        logging.info(f"Found {len(data.get('ProceedingsandOrder', []))} proceedings in current data")
        
        return data
    except Exception as e:
        print(f"ERROR: Failed to fetch Supreme Court data: {e}")
        logging.error(f"Error fetching Supreme Court data: {e}")
        return None

def format_proceeding_for_email(proceeding):
    """Format a proceeding entry for email display"""
    html = f"""
    <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
        <h3 style="color: #d32f2f; margin-top: 0;">New Proceeding - {proceeding['Date']}</h3>
        <p><strong>Description:</strong> {proceeding['Text']}</p>
    """
    
    if 'Links' in proceeding and proceeding['Links']:
        html += "<p><strong>Related Documents:</strong></p><ul>"
        for link in proceeding['Links']:
            html += f"<li><a href=\"{link['DocumentUrl']}\">{link['Description']}: {link['File']}</a></li>"
        html += "</ul>"
    
    html += "</div>"
    return html

def send_alert_email(case_number, case_name, new_proceedings):
    """Send email alert for new proceedings"""
    subject = f"Supreme Court Alert: New Proceedings in {case_name} ({case_number})"
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #1976d2;">Supreme Court Case Update</h2>
        <p><strong>Case:</strong> {case_name}</p>
        <p><strong>Case Number:</strong> {case_number}</p>
        <p><strong>Alert Time:</strong> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
        
        <h3 style="color: #d32f2f;">New Proceedings Detected ({len(new_proceedings)} new entries):</h3>
        
        {''.join([format_proceeding_for_email(proc) for proc in new_proceedings])}
        
        <hr>
        <p style="font-size: 12px; color: #666;">
            This alert was generated automatically by DocketWatch Supreme Court Monitor.<br>
            <a href="https://www.supremecourt.gov/RSS/Cases/JSON/{case_number}.json">View Current JSON Data</a>
        </p>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        logging.info(f"Alert email sent for {len(new_proceedings)} new proceedings in case {case_number}")
        return True
    except Exception as e:
        logging.error(f"Failed to send alert email: {e}")
        return False

def compare_proceedings(previous_data, current_data, case_number):
    """Compare proceedings and identify new ones"""
    new_proceedings = []
    
    print(f"\nComparing proceedings for case {case_number}...")
    logging.info(f"Comparing proceedings for case {case_number}")
    
    if not previous_data or case_number not in previous_data:
        # First time monitoring this case - don't send alerts for existing proceedings
        print(f"First time monitoring case {case_number}. Storing current state without alerts.")
        logging.info(f"First time monitoring case {case_number}. Storing current state without alerts.")
        return new_proceedings
    
    previous_proceedings = previous_data[case_number].get('ProceedingsandOrder', [])
    current_proceedings = current_data.get('ProceedingsandOrder', [])
    
    print(f"Previous proceedings count: {len(previous_proceedings)}")
    print(f"Current proceedings count: {len(current_proceedings)}")
    
    # Convert previous proceedings to a set of unique identifiers
    previous_set = set()
    for proc in previous_proceedings:
        # Use date + first 100 chars of text as unique identifier
        identifier = f"{proc['Date']}:{proc['Text'][:100]}"
        previous_set.add(identifier)
    
    print(f"Previous proceedings identifiers: {len(previous_set)} unique entries")
    
    # Check for new proceedings
    for proc in current_proceedings:
        identifier = f"{proc['Date']}:{proc['Text'][:100]}"
        if identifier not in previous_set:
            new_proceedings.append(proc)
            print(f"NEW PROCEEDING FOUND: {proc['Date']} - {proc['Text'][:50]}...")
            logging.info(f"New proceeding detected: {proc['Date']} - {proc['Text'][:50]}...")
    
    print(f"Total new proceedings found: {len(new_proceedings)}")
    return new_proceedings

def update_monitor_status(cursor, case_number, status, message, proceedings_count=0, last_proceeding_date=None):
    """Update the monitor status in database for dashboard display"""
    try:
        cursor.execute("""
            IF EXISTS (SELECT 1 FROM dbo.supreme_court_monitor_status WHERE case_number = ?)
                UPDATE dbo.supreme_court_monitor_status 
                SET status = ?, 
                    message = ?, 
                    last_check = GETDATE(),
                    proceedings_count = ?,
                    last_proceeding_date = ?
                WHERE case_number = ?
            ELSE
                INSERT INTO dbo.supreme_court_monitor_status 
                (case_number, status, message, last_check, proceedings_count, last_proceeding_date)
                VALUES (?, ?, ?, GETDATE(), ?, ?)
        """, (case_number, status, message, proceedings_count, last_proceeding_date, case_number,
              case_number, status, message, proceedings_count, last_proceeding_date))
        cursor.commit()
    except Exception as e:
        logging.error(f"Error updating monitor status: {e}")

def monitor_case(case_number):
    """Monitor a specific Supreme Court case"""
    global cursor, fk_task_run
    
    print(f"\n{'='*60}")
    print(f"MONITORING SUPREME COURT CASE: {case_number}")
    print(f"{'='*60}")
    
    log_message(cursor, fk_task_run, "INFO", f"Monitoring Supreme Court case {case_number}")
    
    # Load previous data
    previous_data = load_previous_data()
    
    # Fetch current data
    current_data = fetch_supreme_court_data(case_number)
    if not current_data:
        print(f"FAILED to fetch data for case {case_number}")
        log_message(cursor, fk_task_run, "ERROR", f"Failed to fetch data for case {case_number}")
        update_monitor_status(cursor, case_number, "ERROR", f"Failed to fetch data for case {case_number}")
        return False
    
    case_name = f"{current_data.get('PetitionerTitle', 'Unknown')} v. {current_data.get('RespondentTitle', 'Unknown')}"
    print(f"Case Name: {case_name}")
    log_message(cursor, fk_task_run, "INFO", f"Successfully fetched data for {case_name}")
    
    # Get proceedings info for status update
    current_proceedings = current_data.get('ProceedingsandOrder', [])
    proceedings_count = len(current_proceedings)
    last_proceeding_date = current_proceedings[-1]['Date'] if current_proceedings else None
    
    # Compare with previous data
    new_proceedings = compare_proceedings(previous_data, current_data, case_number)
    
    if new_proceedings:
        print(f"\nALERT: Found {len(new_proceedings)} new proceedings in {case_name}")
        log_message(cursor, fk_task_run, "ALERT", f"Found {len(new_proceedings)} new proceedings in {case_name}")
        update_monitor_status(cursor, case_number, "ALERT", f"Found {len(new_proceedings)} new proceedings", proceedings_count, last_proceeding_date)
        
        # Send email alert
        print("Sending email alert...")
        if send_alert_email(case_number, case_name, new_proceedings):
            print("Email alert sent successfully!")
            log_message(cursor, fk_task_run, "INFO", f"Email alert sent successfully for {len(new_proceedings)} new proceedings")
        else:
            print("Failed to send email alert")
            log_message(cursor, fk_task_run, "ERROR", f"Failed to send email alert for new proceedings")
        
        # Store individual proceedings in database
        for proc in new_proceedings:
            try:
                log_id = log_message(cursor, fk_task_run, "ALERT", f"Supreme Court proceeding: {proc['Date']} - {proc['Text'][:100]}")
                # You could insert into case_events table here if you want to track in DB
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Error storing proceeding: {e}")
    else:
        print(f"No new proceedings found for {case_name}")
        log_message(cursor, fk_task_run, "INFO", f"No new proceedings found for {case_name}")
        update_monitor_status(cursor, case_number, "OK", f"No new proceedings - {proceedings_count} total", proceedings_count, last_proceeding_date)
    
    # Save current data for next comparison
    if case_number not in previous_data:
        previous_data[case_number] = {}
    previous_data[case_number] = current_data
    save_current_data(previous_data)
    print(f"Current data saved for next comparison.")
    
    return True

def main():
    global conn, cursor, fk_task_run
    
    print("=" * 80)
    print("SUPREME COURT MONITOR STARTING")
    print("=" * 80)
    
    if is_another_instance_running():
        print("Another instance is already running. Exiting...")
        return
    
    create_lock_file()
    
    try:
        print("Connecting to database...")
        # Database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        cursor = conn.cursor()
        print("Database connection successful")
        
        # Get task run ID
        cursor.execute("""
            SELECT r.id as fk_task_run 
            FROM docketwatch.dbo.task_runs r
            INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
            WHERE s.filename = ? 
            ORDER BY r.id DESC
        """, (script_filename,))
        task_run = cursor.fetchone()
        fk_task_run = task_run[0] if task_run else None
        print(f"Task run ID: {fk_task_run}")
        
        log_message(cursor, fk_task_run, "INFO", "=== Supreme Court Monitor Started ===")
        
        # Cases to monitor (add more case numbers here as needed)
        cases_to_monitor = ["24-1073"]  # Ghislaine Maxwell case
        print(f"Cases to monitor: {cases_to_monitor}")
        
        for case_number in cases_to_monitor:
            try:
                monitor_case(case_number)
                time.sleep(2)  # Brief pause between cases
            except Exception as e:
                print(f"ERROR monitoring case {case_number}: {e}")
                log_message(cursor, fk_task_run, "ERROR", f"Error monitoring case {case_number}: {e}")
        
        print("\n" + "=" * 80)
        print("SUPREME COURT MONITOR COMPLETED SUCCESSFULLY")
        print("=" * 80)
        log_message(cursor, fk_task_run, "INFO", "Supreme Court Monitor completed successfully")
        
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        try:
            log_message(cursor, fk_task_run, "ERROR", f"Supreme Court Monitor failed: {e}")
        except:
            logging.error(f"Supreme Court Monitor failed: {e}")
    
    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        remove_lock_file()

if __name__ == "__main__":
    main()
