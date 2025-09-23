#!/usr/bin/env python3
"""
DocketWatch Enhanced RSS Trigger

OVERVIEW:
Monitors court RSS feeds for new docket entries on tracked PACER cases.
Creates case_events records, sends email alerts, downloads PDFs, and generates AI summaries.

ENHANCED FEATURES:
- Automatic PDF download for new case events
- AI-powered document summarization
- Full workflow automation from RSS discovery to summarized documents

DATABASE TABLES USED:
- docketwatch.dbo.cases
- docketwatch.dbo.courts
- docketwatch.dbo.feed_types
- docketwatch.dbo.rss_feed_entries
- docketwatch.dbo.case_events
- docketwatch.dbo.documents
- docketwatch.dbo.task_runs (+ task_runs_log via scraper_base.log_message)

SCHEDULING:
Safe to run every 15 to 30 minutes. Duplicate detection prevents reprocessing.

DEPENDENCIES:
- requests, bs4, pyodbc, selenium
- scraper_base.log_message
- error_notification_system.create_error_notifier
- summarize_document_event.process_single_pdf
"""

import sys
import os
import re
import time
import smtplib
import logging
import requests
import pyodbc
import subprocess
import tempfile
from pathlib import Path

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
# Enhanced Processing Configuration
# =========================

# Enable PDF download and summarization (set to False to disable)
ENABLE_PDF_DOWNLOAD = True
ENABLE_SUMMARIZATION = True

# Paths to supporting scripts
METADATA_EXTRACTOR_SCRIPT = r"u:\docketwatch\python\extract_pacer_pdf_metadata.py"
PDF_PROCESSOR_SCRIPT = r"u:\docketwatch\python\extract_pacer_pdf_file.py"  # Use the original working script
SUMMARIZER_SCRIPT = r"u:\docketwatch\python\summarize_document_event.py"

# Processing timeouts
PDF_DOWNLOAD_TIMEOUT = 300  # 5 minutes
SUMMARIZATION_TIMEOUT = 120  # 2 minutes

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

def send_enhanced_docket_email(case_name, case_url, event_no, cleaned_docket_text, pdf_summary=None, pdf_paths=None):
    """Send enhanced email alert with PDF summary if available"""
    subject = f"DocketWatch Alert: {case_name} - New Docket Discovered"
    
    # Build email body with optional PDF information
    pdf_section = ""
    if pdf_summary:
        pdf_section = f"""
        <hr>
        <h3>📄 Document Summary</h3>
        <p>{pdf_summary}</p>
        """
    
    if pdf_paths:
        pdf_list = "<br>".join([f"📎 {path}" for path in pdf_paths])
        pdf_section += f"""
        <br><strong>Downloaded Documents:</strong><br>
        {pdf_list}
        """
    
    body = f"""
    <html><body>
        A new docket has been detected for case:<br>
        <a href="{case_url}">{case_name}</a><br><br>
        <strong>Docket No:</strong> {event_no}<br>
        <strong>Description:</strong><br>
        <p>{cleaned_docket_text}</p>
        {pdf_section}
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
        log_message(cursor, fk_task_run, "ALERT", f"Enhanced email sent for new docket in case {case_name}")
        return True
    except Exception as e:
        error_msg = f"Failed to send email for case {case_name}: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("Email Notification Failed", error_msg, fk_task_run=fk_task_run)
        return False

# =========================
# Enhanced Processing Functions
# =========================

def download_pdfs_for_case_event(case_event_id, cursor, fk_task_run):
    """
    Download PDFs for a specific case event using the proven omega approach
    
    Returns:
        tuple: (success, downloaded_paths, error_message)
    """
    if not ENABLE_PDF_DOWNLOAD:
        return True, [], "PDF download disabled"
    
    try:
        log_message(cursor, fk_task_run, "INFO", f"Starting omega approach PDF processing for case event {case_event_id}")
        
        # STEP 1: Always run metadata extraction first (omega approach)
        log_message(cursor, fk_task_run, "INFO", f"Step 1: Running metadata extraction for case event {case_event_id}")
        
        cmd1 = [
            "python", 
            METADATA_EXTRACTOR_SCRIPT, 
            str(case_event_id)
        ]
        
        result1 = subprocess.run(
            cmd1,
            cwd=r"u:\docketwatch\python",
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
        )
        
        if result1.returncode != 0:
            error_msg = f"Metadata extraction failed: {result1.stderr}"
            log_message(cursor, fk_task_run, "WARNING", error_msg)
            return False, [], error_msg
        
        log_message(cursor, fk_task_run, "INFO", f"Metadata extraction completed for case event {case_event_id}")
        
        # Wait before next step (omega timing)
        time.sleep(3)
        
        # STEP 2: Run PDF download (omega approach)
        log_message(cursor, fk_task_run, "INFO", f"Step 2: Running PDF download for case event {case_event_id}")
        
        cmd2 = [
            "python", 
            PDF_PROCESSOR_SCRIPT, 
            str(case_event_id)
        ]
        
        result2 = subprocess.run(
            cmd2,
            cwd=r"u:\docketwatch\python",
            capture_output=True,
            text=True,
            timeout=PDF_DOWNLOAD_TIMEOUT
        )
        
        if result2.returncode == 0:
            log_message(cursor, fk_task_run, "INFO", f"PDF download completed using omega approach for case event {case_event_id}")
            
            # Query for downloaded documents
            cursor.execute("""
                SELECT rel_path FROM docketwatch.dbo.documents 
                WHERE fk_case_event = ? AND rel_path IS NOT NULL AND rel_path != 'pending'
            """, (case_event_id,))
            
            downloaded_paths = [row[0] for row in cursor.fetchall()]
            return True, downloaded_paths, None
            
        else:
            error_msg = f"PDF download failed: {result2.stderr}"
            log_message(cursor, fk_task_run, "WARNING", error_msg)
            return False, [], error_msg
            
    except subprocess.TimeoutExpired:
        error_msg = f"PDF processing timeout for case event {case_event_id}"
        log_message(cursor, fk_task_run, "WARNING", error_msg)
        return False, [], error_msg
        
    except Exception as e:
        error_msg = f"PDF processing error for case event {case_event_id}: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("PDF Processing Failed", error_msg, fk_task_run=fk_task_run)
        return False, [], error_msg

def summarize_documents_for_case_event(case_event_id, cursor, fk_task_run):
    """
    Generate AI summaries for documents in a case event
    
    Returns:
        tuple: (success, summary_text, error_message)
    """
    if not ENABLE_SUMMARIZATION:
        return True, None, "Summarization disabled"
    
    try:
        log_message(cursor, fk_task_run, "INFO", f"Starting document summarization for case event {case_event_id}")
        
        # Get documents that need summarization
        cursor.execute("""
            SELECT doc_uid FROM docketwatch.dbo.documents 
            WHERE fk_case_event = ? 
            AND rel_path IS NOT NULL 
            AND rel_path != 'pending'
            AND summary_ai IS NULL
            AND ocr_text IS NOT NULL
        """, (case_event_id,))
        
        documents = cursor.fetchall()
        
        if not documents:
            log_message(cursor, fk_task_run, "INFO", f"No documents to summarize for case event {case_event_id}")
            return True, None, "No documents requiring summarization"
        
        summaries = []
        
        for doc_row in documents:
            doc_uid = str(doc_row[0])
            
            try:
                # Import the summarization function
                from summarize_document_event import process_single_pdf
                
                log_message(cursor, fk_task_run, "INFO", f"Summarizing document {doc_uid}")
                
                # Process the document
                process_single_pdf(doc_uid)
                
                # Get the generated summary
                cursor.execute("""
                    SELECT summary_ai FROM docketwatch.dbo.documents 
                    WHERE doc_uid = ?
                """, (doc_uid,))
                
                summary_row = cursor.fetchone()
                if summary_row and summary_row[0]:
                    summaries.append(summary_row[0])
                    log_message(cursor, fk_task_run, "INFO", f"Successfully summarized document {doc_uid}")
                else:
                    log_message(cursor, fk_task_run, "WARNING", f"No summary generated for document {doc_uid}")
                    
            except Exception as doc_error:
                error_msg = f"Failed to summarize document {doc_uid}: {doc_error}"
                log_message(cursor, fk_task_run, "WARNING", error_msg)
                continue
        
        # Combine summaries if multiple documents
        if summaries:
            combined_summary = "\n\n".join(summaries)
            log_message(cursor, fk_task_run, "INFO", 
                       f"Generated {len(summaries)} summaries for case event {case_event_id}")
            return True, combined_summary, None
        else:
            return True, None, "No summaries generated"
            
    except Exception as e:
        error_msg = f"Summarization error for case event {case_event_id}: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("Document Summarization Failed", error_msg, fk_task_run=fk_task_run)
        return False, None, error_msg

def process_new_case_event(case_event_id, case_name, event_no, event_description, event_url, cursor, fk_task_run):
    """
    Complete processing workflow for a new case event:
    1. Download PDFs
    2. Generate summaries
    3. Send enhanced email alert
    """
    log_message(cursor, fk_task_run, "INFO", 
               f"Starting enhanced processing for case event {case_event_id}")
    
    pdf_paths = []
    pdf_summary = None
    
    # Step 1: Download PDFs
    if ENABLE_PDF_DOWNLOAD:
        pdf_success, pdf_paths, pdf_error = download_pdfs_for_case_event(case_event_id, cursor, fk_task_run)
        if not pdf_success:
            log_message(cursor, fk_task_run, "WARNING", 
                       f"PDF download failed for case event {case_event_id}: {pdf_error}")
        
        # Small delay to allow for file system updates
        time.sleep(2)
    
    # Step 2: Generate summaries
    if ENABLE_SUMMARIZATION and pdf_paths:
        summary_success, pdf_summary, summary_error = summarize_documents_for_case_event(case_event_id, cursor, fk_task_run)
        if not summary_success:
            log_message(cursor, fk_task_run, "WARNING", 
                       f"Summarization failed for case event {case_event_id}: {summary_error}")
    
    # Step 3: Send enhanced email alert
    try:
        send_enhanced_docket_email(
            case_name=case_name,
            case_url=event_url,
            event_no=event_no,
            cleaned_docket_text=event_description,
            pdf_summary=pdf_summary,
            pdf_paths=pdf_paths
        )
    except Exception as email_error:
        log_message(cursor, fk_task_run, "WARNING", f"Email send failed: {email_error}")
    
    log_message(cursor, fk_task_run, "INFO", 
               f"Enhanced processing completed for case event {case_event_id}")

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
        WHERE s.filename = ? OR s.filename LIKE '%rss%trigger%'
        ORDER BY r.id DESC
    """, (script_filename,))
    task_run = cursor.fetchone()
    fk_task_run = task_run[0] if task_run else None
    
    # If no exact match, try to find any RSS-related task run
    if not fk_task_run:
        cursor.execute("""
            SELECT TOP 1 r.id as fk_task_run
            FROM docketwatch.dbo.task_runs r
            INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
            WHERE s.filename LIKE '%rss%'
            ORDER BY r.id DESC
        """)
        task_run = cursor.fetchone()
        fk_task_run = task_run[0] if task_run else None
        
except Exception as e:
    error_msg = f"Could not resolve fk_task_run: {e}"
    print(f"WARNING: {error_msg}")
    fk_task_run = None

if not fk_task_run:
    # For enhanced RSS trigger, we'll create a fallback task run entry
    print("WARNING: fk_task_run could not be determined, using fallback")
    try:
        # Find or create a scheduled task for this script
        cursor.execute("""
            SELECT id FROM docketwatch.dbo.scheduled_task 
            WHERE filename = ?
        """, (script_filename,))
        
        scheduled_task = cursor.fetchone()
        if not scheduled_task:
            # Create a scheduled task entry
            cursor.execute("""
                INSERT INTO docketwatch.dbo.scheduled_task (filename, description, active)
                OUTPUT INSERTED.id
                VALUES (?, 'Enhanced RSS Trigger with PDF Download and Summarization', 1)
            """, (script_filename,))
            scheduled_task_id = cursor.fetchone()[0]
        else:
            scheduled_task_id = scheduled_task[0]
        
        # Create a task run entry
        cursor.execute("""
            INSERT INTO docketwatch.dbo.task_runs (fk_scheduled_task, start_time, status)
            OUTPUT INSERTED.id
            VALUES (?, GETDATE(), 'Running')
        """, (scheduled_task_id,))
        fk_task_run = cursor.fetchone()[0]
        conn.commit()
        print(f"Created fallback task run ID: {fk_task_run}")
        
    except Exception as create_error:
        print(f"ERROR: Could not create fallback task run: {create_error}")
        fk_task_run = 1  # Ultimate fallback

print(f"Resolved fk_task_run: {fk_task_run}")
log_message(cursor, fk_task_run, "INFO", f"Enhanced RSS trigger script started.")

# =========================
# Simple Helper Functions
# =========================

def safe_int(val, default=None):
    try:
        return int(val)
    except Exception:
        return default

# =========================
# Main Enhanced RSS Monitoring Loop
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
                        
                        # Insert case event and get the ID
                        cursor.execute("""
                            INSERT INTO docketwatch.dbo.case_events
                              (event_date, event_no, event_description, fk_cases, status, fk_task_run_log, event_url)
                            OUTPUT INSERTED.id
                            VALUES (?, ?, ?, ?, 'RSS Detected', ?, ?)
                        """, (pub_date, event_no, event_description, fk_case, log_id, event_url))

                        case_event_id = cursor.fetchone()[0]
                        conn.commit()

                        # Start enhanced processing workflow
                        try:
                            process_new_case_event(
                                case_event_id=case_event_id,
                                case_name=db_case_name,
                                event_no=event_no,
                                event_description=event_description,
                                event_url=event_url,
                                cursor=cursor,
                                fk_task_run=fk_task_run
                            )
                        except Exception as processing_error:
                            log_message(cursor, fk_task_run, "ERROR", 
                                       f"Enhanced processing failed for case event {case_event_id}: {processing_error}")
                            # Still send basic email as fallback
                            try:
                                send_enhanced_docket_email(db_case_name, event_url, event_no, event_description)
                            except Exception:
                                pass

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

    log_message(cursor, fk_task_run, "INFO", "Enhanced RSS trigger script completed successfully.")

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
        additional_context="Enhanced RSS trigger script failed at top-level main loop"
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

print("\nEnhanced RSS Trigger script completed.")