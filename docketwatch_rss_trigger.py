#!/usr/bin/env python3
"""
DocketWatch RSS Trigger - Simplified Version

OVERVIEW:
Monitors court RSS feeds for new docket entries on tracked PACER cases.
Creates basic case_events records and sends email alerts.
Relies on separate scheduled scripts for PACER scraping and document processing.

DATABASE TABLES USED:
- docketwatch.dbo.cases
- docketwatch.dbo.courts
- docketwatch.dbo.feed_types
- docketwatch.dbo.rss_feed_entries
- docketwatch.dbo.case_events
- docketwatch.dbo.task_runs (+ task_runs_log via scraper_base.log_message)

SCHEDULING:
Safe to run every 15 to 30 minutes. Duplicate detection prevents reprocessing.

DEPENDENCIES:
- requests
- bs4
- pyodbc
- scraper_base.log_message
- error_notification_system.create_error_notifier
"""

import sys
import os
import re
import time
import smtplib
import logging
import requests
import pyodbc

from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime

from scraper_base import log_message
from error_notification_system import create_error_notifier

# =========================
# Script + Logging Setup
# =========================

script_filename = os.path.splitext(os.path.basename(__file__))[0]
error_notifier = create_error_notifier(script_filename)

LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print(f"Script filename: {script_filename}")
print(f"Logging to: {LOG_FILE}")

# =========================
# Email Configuration
# =========================

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

def send_docket_email(case_name, case_url, event_no, cleaned_docket_text):
    subject = f"DocketWatch Alert: {case_name} - New Docket Discovered"
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
        log_message(cursor, fk_task_run, "ALERT", f"Email sent for new docket in case {case_name}")
    except Exception as e:
        error_msg = f"Failed to send email for case {case_name}: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("Email Notification Failed", error_msg, fk_task_run=fk_task_run)

# =========================
# DB Connection + Task Run
# =========================

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    print("Database connection successful.")
except pyodbc.Error as ex:
    error_msg = f"Database connection failed: {ex}"
    print(f"CRITICAL: {error_msg}")
    error_notifier.log_database_error(error_msg)
    sys.exit()

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

# =========================
# Simple Helper Functions
# =========================

def safe_int(val, default=None):
    try:
        return int(val)
    except Exception:
        return default
# =========================
# Main RSS Monitoring Loop
# =========================

try:
    PACER_TOOL_ID = 2  # PACER tool ID
    
    # Preload tracked PACER cases
    log_message(cursor, fk_task_run, "INFO", "Fetching tracked PACER cases...")
    cursor.execute("""
        SELECT id, pacer_id, case_name
        FROM docketwatch.dbo.cases
        WHERE fk_tool = ? AND status = 'Tracked' AND pacer_id IS NOT NULL
    """, (PACER_TOOL_ID,))
    tracked_cases_map = {row.pacer_id: (row.id, row.case_name) for row in cursor.fetchall()}
    log_message(cursor, fk_task_run, "INFO", f"Monitoring {len(tracked_cases_map)} tracked cases.")

    # Load court RSS sources
    cursor.execute("""
        SELECT crt.court_code, crt.pacer_url, ft.url_suffix
        FROM docketwatch.dbo.courts crt
        LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
        WHERE crt.pacer_url IS NOT NULL AND crt.fk_feed_type <> 0
    """)
    sites = cursor.fetchall()

    for court_code, base_url, url_suffix in sites:
        rss_url = ""
        try:
            rss_url = base_url.rstrip("/") + (url_suffix or "/cgi-bin/rss_outside.pl")
            log_message(cursor, fk_task_run, "INFO", f"Checking RSS feed: {rss_url}")

            try:
                response = requests.get(rss_url, timeout=20)
            except requests.exceptions.Timeout:
                msg = f"Timeout accessing RSS feed: {rss_url}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Timeout", msg, fk_task_run=fk_task_run)
                continue
            except requests.exceptions.RequestException as e:
                msg = f"Network error accessing RSS feed {rss_url}: {e}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Network Error", msg, fk_task_run=fk_task_run)
                continue

            if response.status_code != 200:
                msg = f"HTTP {response.status_code} from {rss_url}"
                log_message(cursor, fk_task_run, "WARNING", msg)
                if response.status_code >= 500:
                    error_notifier.log_error("RSS Feed Server Error", msg, fk_task_run=fk_task_run)
                continue

            try:
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
            except Exception as e:
                msg = f"Failed to parse XML from RSS feed {rss_url}: {e}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Parse Error", msg, fk_task_run=fk_task_run)
                continue

            if not items:
                log_message(cursor, fk_task_run, "INFO", f"No entries in RSS feed for {court_code}")
            else:
                log_message(cursor, fk_task_run, "INFO", f"Found {len(items)} entries in RSS feed for {court_code}")

            for item in items:
                link = item.link.text.strip() if item.link else None
                if not link:
                    continue

                # Extract PACER id from link (pattern: ?<id>)
                m = re.search(r"\?(\d+)", link)
                if not m:
                    continue
                pacer_id = safe_int(m.group(1))
                if pacer_id is None or pacer_id not in tracked_cases_map:
                    continue

                fk_case, db_case_name = tracked_cases_map[pacer_id]

                guid = item.guid.text.strip() if item.guid else None
                if not guid:
                    continue

                # Skip if we have already processed this GUID
                cursor.execute("SELECT id FROM docketwatch.dbo.rss_feed_entries WHERE guid = ?", (guid,))
                if cursor.fetchone():
                    continue

                pub_date = parsedate_to_datetime(item.pubDate.text.strip()) if item.pubDate else None
                desc_raw = item.description.text.strip() if item.description else ""

                # Quick pulls from the common PACER RSS formatting
                event_description_match = re.search(r'\[(.*?)\]', desc_raw)
                event_description = event_description_match.group(1) if event_description_match else ""

                event_no_match = re.search(r'>(\d+)</a>', desc_raw)
                event_no = safe_int(event_no_match.group(1)) if event_no_match else None
                if event_no is None:
                    # If we cannot find an event number, still log rss entry but skip case_events insert
                    event_no = -1  # diagnostic value

                event_url_match = re.search(r'href="([^"]+)"', desc_raw)
                event_url = event_url_match.group(1) if event_url_match else link

                title = item.title.text.strip() if item.title else ""
                case_number, case_name_from_title = (title.split(" ", 1) if " " in title else ("", title))

                # Insert rss_feed_entries
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.rss_feed_entries
                      (fk_court, case_number, case_name, event_description, event_no, pub_date, guid, link, pacer_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (court_code, case_number, case_name_from_title, event_description, event_no, pub_date, guid, link, pacer_id))

                # Insert case_event if not present for this event_no
                if event_no != -1:
                    cursor.execute("""
                        SELECT COUNT(*) FROM docketwatch.dbo.case_events
                        WHERE fk_cases = ? AND event_no = ?
                    """, (fk_case, event_no))
                    exists = cursor.fetchone()[0] > 0

                    if not exists:
                        log_id = log_message(cursor, fk_task_run, "ALERT",
                                             f"New RSS docket for {db_case_name} - Event No: {event_no}",
                                             fk_case=fk_case)
                        cursor.execute("""
                            INSERT INTO docketwatch.dbo.case_events
                              (event_date, event_no, event_description, fk_cases, status, fk_task_run_log, event_url)
                            VALUES (?, ?, ?, ?, 'RSS Detected', ?, ?)
                        """, (pub_date, event_no, event_description, fk_case, log_id, event_url))

                        conn.commit()

                        # Send email alert
                        try:
                            send_docket_email(db_case_name, event_url, event_no, event_description)
                        except Exception as email_err:
                            # Non-fatal email error
                            log_message(cursor, fk_task_run, "WARNING", f"Email send failed: {email_err}")
                    else:
                        conn.commit()
                        log_message(cursor, fk_task_run, "INFO",
                                    f"Duplicate event_no {event_no} for case {db_case_name}. Skipping.",
                                    fk_case=fk_case)
                else:
                    conn.commit()
                    log_message(cursor, fk_task_run, "WARNING",
                                f"RSS item missing event_no; recorded feed entry only for case {db_case_name}.",
                                fk_case=fk_case)

        except Exception as e:
            msg = f"Unexpected error processing RSS feed {rss_url}: {e}"
            log_message(cursor, fk_task_run, "ERROR", msg)
            error_notifier.log_error("RSS Processing Error", msg, fk_task_run=fk_task_run)
            continue

    log_message(cursor, fk_task_run, "INFO", "RSS trigger script completed successfully.")

except Exception as e:
    error_msg = f"Critical script failure in main loop: {str(e)}"
    print(f"CRITICAL: {error_msg}")
    try:
        log_message(cursor, fk_task_run, "ERROR", error_msg)
    except Exception:
        pass
    error_notifier.log_critical_error(
        error_msg,
        fk_task_run=fk_task_run,
        additional_context="RSS trigger script failed at top-level main loop"
    )
    raise
# =========================
# Final Cleanup
# =========================
finally:
    try:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    except Exception as cleanup_error:
        error_msg = f"Error during database cleanup: {cleanup_error}"
        print(f"ERROR: {error_msg}")
        try:
            error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)
        except:
            pass

print("\nRSS Trigger script completed.")
