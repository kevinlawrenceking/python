import sys
import requests
import pyodbc
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
import re
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from scraper_base import log_message
from error_notification_system import create_error_notifier

# === Script + Logging Setup ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# === Initialize error notification system ===
error_notifier = create_error_notifier(script_filename)

LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

print(f"Script filename: {script_filename}")
print(f"Logging to: {LOG_FILE}")

# --- Email Configuration ---
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

# --- CORRECTED Email Function ---
# Reverted to original signature, using global cursor and fk_task_run
def send_docket_email(case_name, case_url, event_no, cleaned_docket_text):
    subject = f"DocketWatch Alert: {case_name} – New Docket Discovered"
    body = f"""
    <html><body>
        A new docket has been detected for case:<br>
        <a href="{case_url}">{case_name}</a><br><br>
        <strong>Docket No:</strong> {event_no}<br>
        <strong>Description:</strong><br>
        <p>{cleaned_docket_text}</p>
    </body></html>
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        # Uses the global variables as intended
        log_message(cursor, fk_task_run, "ALERT", f"Email sent for new docket in case {case_name}", fk_case=None)
    except Exception as e:
        error_msg = f"Failed to send email for case {case_name}: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=None)
        error_notifier.log_error("Email Notification Failed", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}")

# === DB Connection ===
try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    print("Database connection successful.")
except pyodbc.Error as ex:
    error_msg = f"Database connection failed: {ex}"
    print(f"CRITICAL: {error_msg}")
    error_notifier.log_database_error(error_msg)
    sys.exit()

# === Resolve Task Run ID ===
try:
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
    error_msg = f"Could not resolve fk_task_run: {e}"
    print(f"CRITICAL: {error_msg}")
    error_notifier.log_database_error(error_msg)
    fk_task_run = None

if not fk_task_run:
    error_msg = "fk_task_run could not be determined"
    print(f"CRITICAL: {error_msg}")
    error_notifier.log_critical_error(error_msg)
    sys.exit()

print(f"Resolved fk_task_run: {fk_task_run}")
log_message(cursor, fk_task_run, "INFO", f"Script {script_filename} started.")

# Wrap the entire main processing in error handling
try:
    # === OPTIMIZATION: Fetch all tracked cases ONCE ===
    print("Fetching list of all tracked cases from the database...")
    try:
        cursor.execute("""
            SELECT id, pacer_id, case_name 
            FROM docketwatch.dbo.cases 
            WHERE fk_tool = 2 AND status = 'Tracked' AND pacer_id IS NOT NULL
        """)
        tracked_cases_map = {row.pacer_id: (row.id, row.case_name) for row in cursor.fetchall()}
        log_message(cursor, fk_task_run, "INFO", f"Monitoring {len(tracked_cases_map)} tracked cases.")
        print(f"Monitoring {len(tracked_cases_map)} tracked cases.")
    except Exception as e:
        error_msg = f"Failed to fetch tracked cases from database: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
        raise

    # === Load Court RSS Sources ===
    try:
        cursor.execute("""
            SELECT crt.court_code, crt.pacer_url, ft.url_suffix
            FROM docketwatch.dbo.courts crt
            LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
            WHERE crt.pacer_url IS NOT NULL AND crt.fk_feed_type <> 0
        """)
        sites = cursor.fetchall()
    except Exception as e:
        error_msg = f"Failed to fetch court RSS sources from database: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
        raise

    # === Main Processing Loop ===
    for court_code, base_url, url_suffix in sites:
        rss_url = "" # Define here to be available in exception block
        try:
            rss_url = base_url.rstrip("/") + (url_suffix or "/cgi-bin/rss_outside.pl")
            print(f"\nChecking RSS feed for: {rss_url}")
            log_message(cursor, fk_task_run, "INFO", f"Checking RSS feed for: {rss_url}")

            try:
                response = requests.get(rss_url, timeout=20)
            except requests.exceptions.Timeout:
                error_msg = f"Timeout accessing RSS feed: {rss_url}"
                print(f"   ERROR: {error_msg}")
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error("RSS Feed Timeout", error_msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error accessing RSS feed {rss_url}: {e}"
                print(f"   ERROR: {error_msg}")
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error("RSS Feed Network Error", error_msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code} from {rss_url}"
                print(f"   WARNING: {error_msg}")
                log_message(cursor, fk_task_run, "WARNING", error_msg)
                # Don't send email notification for HTTP errors unless it's severe
                if response.status_code >= 500:
                    error_notifier.log_error("RSS Feed Server Error", error_msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue

            try:
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
            except Exception as e:
                error_msg = f"Failed to parse XML from RSS feed {rss_url}: {e}"
                print(f"   ERROR: {error_msg}")
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                error_notifier.log_error("RSS Feed Parse Error", error_msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue
            if not items:
                log_message(cursor, fk_task_run, "INFO", f"No entries in RSS feed for {court_code}")
            else:
                log_message(cursor, fk_task_run, "INFO", f"Found {len(items)} entries in RSS feed for {court_code}")

            for item in items:
                link = item.link.text.strip() if item.link else None
                if not link: continue

                match = re.search(r"\?(\d+)", link)
                if not match: continue
                pacer_id = int(match.group(1))

                if pacer_id in tracked_cases_map:
                    fk_case, db_case_name = tracked_cases_map[pacer_id]
                    guid = item.guid.text.strip() if item.guid else None
                    if not guid: continue
                    
                    try:
                        cursor.execute("SELECT id FROM docketwatch.dbo.rss_feed_entries WHERE guid = ?", (guid,))
                        if cursor.fetchone():
                            continue

                        pub_date = parsedate_to_datetime(item.pubDate.text.strip()) if item.pubDate else None
                        desc_raw = item.description.text.strip() if item.description else ""
                        event_description_match = re.search(r'\[(.*?)\]', desc_raw)
                        event_description = event_description_match.group(1) if event_description_match else None
                        event_no_match = re.search(r'>(\d+)</a>', desc_raw)
                        event_no = int(event_no_match.group(1)) if event_no_match else None
                        event_url_match = re.search(r'href="([^"]+)"', desc_raw)
                        event_url = event_url_match.group(1) if event_url_match else None
                        title = item.title.text.strip() if item.title else ""
                        case_number, case_name = title.split(" ", 1) if " " in title else ("", title)

                        cursor.execute("""
                            INSERT INTO docketwatch.dbo.rss_feed_entries (fk_court, case_number, case_name, event_description, event_no, pub_date, guid, link, pacer_id) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (court_code, case_number, case_name, event_description, event_no, pub_date, guid, link, pacer_id))
                        
                        cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.case_events WHERE fk_cases = ? AND event_no = ?", (fk_case, event_no))
                        if cursor.fetchone()[0] == 0:
                            print(f"   New event found for case '{db_case_name}'. Inserting into case_events.")
                            log_id = log_message(cursor, fk_task_run, "ALERT", f"New RSS docket for {db_case_name} – Event No: {event_no}", fk_case=fk_case)

                            cursor.execute("""
                                INSERT INTO docketwatch.dbo.case_events (event_date, event_no, event_description, fk_cases, status, fk_task_run_log, event_url) 
                                VALUES (?, ?, ?, ?, 'RSS Pending', ?, ?)
                            """, (pub_date, event_no, event_description, fk_case, log_id, event_url))
                            
                            conn.commit()
                            print(f"   Inserted event_no {event_no} for case '{db_case_name}'")
                            # Corrected the call to match the original function signature
                            send_docket_email(db_case_name, event_url, event_no, event_description)
                        else:
                            conn.commit()
                            log_message(cursor, fk_task_run, "INFO", f"Duplicate event_no {event_no} for case {db_case_name}. Skipping.")
                    
                    except Exception as db_error:
                        error_msg = f"Database error processing RSS item for case {db_case_name} (pacer_id: {pacer_id}): {db_error}"
                        print(f"   ERROR: {error_msg}")
                        log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=fk_case)
                        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run, fk_case=fk_case, additional_context=f"Case: {db_case_name}, Court: {court_code}")
                        continue

        except Exception as e:
            error_msg = f"Unexpected error processing RSS feed {rss_url}: {e}"
            print(f"   ERROR: {error_msg}")
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            error_notifier.log_error("RSS Processing Error", error_msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}, URL: {rss_url}")
            continue
        
    # Script completed successfully
    log_message(cursor, fk_task_run, "INFO", "RSS trigger script completed successfully.")

except Exception as e:
    # Handle any unhandled exceptions at the top level
    error_msg = f"Critical script failure: {str(e)}"
    print(f"CRITICAL: {error_msg}")
    try:
        log_message(cursor, fk_task_run, "ERROR", error_msg)
    except:
        pass  # Don't fail if logging fails
    
    error_notifier.log_critical_error(
        error_msg, 
        fk_task_run=fk_task_run,
        additional_context="RSS trigger script failed at top level - check logs for details"
    )
    raise

finally:
    # === Final Cleanup ===
    try:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    except Exception as cleanup_error:
        error_msg = f"Error during database cleanup: {cleanup_error}"
        print(f"ERROR: {error_msg}")
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)

print("\nScript finished.")
