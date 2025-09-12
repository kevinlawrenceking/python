#!/usr/bin/env python3
"""
DocketWatch RSS Trigger + End-to-End Orchestrator

OVERVIEW:
Monitors court RSS feeds for new docket entries on tracked PACER cases.
On discovering a new event, it immediately orchestrates:
  - PACER scrape refresh for that case
  - Event long-description enrichment
  - Document discovery and PDF downloads
  - OCR discovery to queue new PDFs
  - Gemini case-leve        # Extract filename from rel_path
        file_name = os.path.basename(rel_path) if rel_path else f"E{doc_id or doc_uid[:8]}.pdf"summary generation

DATABASE TABLES USED:
- docketwatch.dbo.cases
- docketwatch.dbo.courts
- docketwatch.dbo.feed_types
- docketwatch.dbo.rss_feed_entries
- docketwatch.dbo.case_events
- docketwatch.dbo.documents    (unified docs table; adapt if still migrating)
- docketwatch.dbo.task_runs (+ task_runs_log via scraper_base.log_message)

SCHEDULING:
Safe to run every 15 to 30 minutes. Duplicate detection prevents reprocessing.

DEPENDENCIES:
- requests
- bs4
- pyodbc
- scraper_base.log_message
- error_notification_system.create_error_notifier
- subprocess to invoke your existing PACER scraper, OCR finder, and summarizer
"""

import sys
import os
import re
import time
import smtplib
import logging
import subprocess
import requests
import pyodbc
import uuid

from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs

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
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
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

# =========================
# PACER Identifier Extraction
# =========================

def safe_log_message(message):
    """
    Safely handle Unicode characters in log messages.
    Replaces problematic Unicode characters with ASCII equivalents.
    """
    # Common Unicode replacements for logging
    unicode_replacements = {
        '✅': '[OK]',
        '❌': '[ERROR]',
        '🔍': '[INFO]',
        '📋': '[DATA]',
        '🔔': '[ALERT]',
        '⚠️': '[WARNING]',
        '🎯': '[TARGET]',
        '🚀': '[SUCCESS]'
    }
    
    safe_message = str(message)
    for unicode_char, ascii_replacement in unicode_replacements.items():
        safe_message = safe_message.replace(unicode_char, ascii_replacement)
    
    return safe_message


def extract_pacer_identifiers(event_description, event_url):
    """
    Extract PACER document identifiers for bulletproof duplicate detection.
    Returns (pacer_doc_number, pacer_doc_id) tuple.
    """
    import re
    
    pacer_doc_number = None  # The document number like "73"
    pacer_doc_id = None      # The unique PACER ID like "127138195871"
    
    # Extract document number from description
    # Look for patterns like "Document 73", "Doc 73", or just number in anchor context
    doc_patterns = [
        r'(?:Document|Doc)\s+(\d+)',  # "Document 73"
        r'<a[^>]*>(\d+)</a>',         # "<a>73</a>"
        r'(?:Entry|Event)\s+(\d+)',   # "Entry 73"
    ]
    
    for pattern in doc_patterns:
        match = re.search(pattern, event_description, re.IGNORECASE)
        if match:
            pacer_doc_number = int(match.group(1))
            break
    
    # Extract PACER document ID from URL
    if event_url and '/doc1/' in event_url:
        try:
            pacer_doc_id = event_url.split('/doc1/')[1].split('?')[0].split('/')[0]
        except:
            pass
    
    return pacer_doc_number, pacer_doc_id


def bulletproof_duplicate_check(cursor, fk_case, pacer_doc_number, pacer_doc_id):
    """
    Bulletproof duplicate detection using documents table PACER identifiers.
    Returns (exists, case_event_id) tuple.
    """
    
    # Method 1: Check by doc_id (most reliable - has unique constraint)
    if pacer_doc_id:
        cursor.execute("""
            SELECT ce.id FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.documents d ON d.fk_case_event = ce.id
            WHERE d.doc_id = ? AND ce.fk_cases = ?
        """, (pacer_doc_id, fk_case))
        
        result = cursor.fetchone()
        if result:
            print(f"[OK] Found existing event by doc_id: {pacer_doc_id}")
            return True, result[0]
    
    # Method 2: Check by pdf_no (PACER document number)
    if pacer_doc_number:
        cursor.execute("""
            SELECT ce.id FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.documents d ON d.fk_case_event = ce.id
            WHERE d.pdf_no = ? AND ce.fk_cases = ?
        """, (pacer_doc_number, fk_case))
        
        result = cursor.fetchone()
        if result:
            print(f"[OK] Found existing event by pdf_no: {pacer_doc_number}")
            return True, result[0]
    
    # Method 3: Check by URL pattern (additional safety)
    if pacer_doc_id:
        cursor.execute("""
            SELECT ce.id FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.documents d ON d.fk_case_event = ce.id
            WHERE d.pdf_url LIKE ? AND ce.fk_cases = ?
        """, (f'%/doc1/{pacer_doc_id}%', fk_case))
        
        result = cursor.fetchone()
        if result:
            print(f"[OK] Found existing event by URL pattern: {pacer_doc_id}")
            return True, result[0]
    
    return False, None


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
        log_message(cursor, fk_task_run, "ALERT", f"Email sent for new docket in case {case_name}", fk_case=None)
    except Exception as e:
        error_msg = f"Failed to send email for case {case_name}: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg, fk_case=None)
        error_notifier.log_error("Email Notification Failed", error_msg, fk_task_run=fk_task_run, additional_context=f"Case: {case_name}")

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
# Orchestration Config
# =========================

PACER_TOOL_ID = 2  # PACER
SCRAPER_SCRIPT = r"\\10.146.176.84\general\docketwatch\python\docketwatch_pacer_scraper_v2.py"
PDF_ROOT = r"\\10.146.176.84\general\docketwatch\docs\cases"
OCR_TRIGGER = r"\\10.146.176.84\general\docketwatch\python\final_pdfs_finder.py"
SUMMARIZER = r"\\10.146.176.84\general\docketwatch\python\pacer_case_summarizer.py"

DOWNLOAD_TIMEOUT = 60
SCRAPER_COOLDOWN_SEC = 5
OCR_SUMMARY_COOLDOWN_SEC = 2

# =========================
# Common Helpers
# =========================

def safe_int(val, default=None):
    try:
        return int(val)
    except Exception:
        return default

def extract_doc_id_from_url(url: str):
    if not url:
        return None
    qs = parse_qs(urlparse(url).query)
    for key in ("doc1", "document_id", "DLS_id", "docid"):
        if key in qs and qs[key]:
            return qs[key][0]
    return None

def run_subprocess(cmd_list, phase_name, fk_case=None):
    start = time.time()
    try:
        p = subprocess.run(cmd_list, capture_output=True, text=True, timeout=600)
        ok = (p.returncode == 0)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        msg = f"{phase_name} return={p.returncode}; out={out[:600]}{'...' if len(out)>600 else ''}; err={err[:600]}{'...' if len(err)>600 else ''}"
        level = "INFO" if ok else "ERROR"
        log_message(cursor, fk_task_run, level, msg, fk_case=fk_case)
        if not ok:
            error_notifier.log_error(f"{phase_name} failed", msg, fk_task_run=fk_task_run, fk_case=fk_case)
        return ok
    except subprocess.TimeoutExpired as te:
        msg = f"{phase_name} timed out: {te}"
        log_message(cursor, fk_task_run, "ERROR", msg, fk_case=fk_case)
        error_notifier.log_error(f"{phase_name} timeout", msg, fk_task_run=fk_task_run, fk_case=fk_case)
        return False
    except Exception as e:
        msg = f"{phase_name} exception: {e}"
        log_message(cursor, fk_task_run, "ERROR", msg, fk_case=fk_case)
        error_notifier.log_error(f"{phase_name} exception", msg, fk_task_run=fk_task_run, fk_case=fk_case)
        return False

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Could not create directory {path}: {e}")

def download_pdf(url, local_path, max_retries=3):
    """Download PDF with retry logic and better error handling"""
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT, headers=headers) as r:
                r.raise_for_status()
                
                # Check if response is actually a PDF
                content_type = r.headers.get('Content-Type', '').lower()
                if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
                    return False, f"Invalid content type: {content_type}"
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Verify file was written and has reasonable size
                if os.path.exists(local_path):
                    file_size = os.path.getsize(local_path)
                    if file_size < 100:  # Less than 100 bytes probably indicates an error page
                        os.remove(local_path)
                        return False, f"Downloaded file too small ({file_size} bytes) - likely an error page"
                    return True, None
                else:
                    return False, "File was not created successfully"
                    
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return False, f"Timeout after {max_retries} attempts"
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return False, f"Request failed after {max_retries} attempts: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    return False, f"Failed after {max_retries} attempts"

def refresh_case_via_pacer_scraper(fk_case: int):
    # Use the working docketwatch_pacer_scraper_v2 with priority=1 and specific case ID
    cmd = ["python", SCRAPER_SCRIPT, "1", str(fk_case)]
    return run_subprocess(cmd, "PACER scrape", fk_case=fk_case)

def trigger_ocr_discovery():
    cmd = ["python", OCR_TRIGGER]
    return run_subprocess(cmd, "OCR discovery")

def trigger_case_summary(fk_case: int):
    cmd = ["python", SUMMARIZER, "--case-id", str(fk_case)]
    return run_subprocess(cmd, "Gemini summarizer", fk_case=fk_case)
# =========================
# Event and Document Enrichment
# =========================

def enrich_event_from_fresh_pacer(cursor, fk_case: int, event_no: int):
    """
    After the PACER scrape, pull the latest long description for the event_no
    and return (case_event_id, long_desc). Assumes the scraper wrote into case_events.
    """
    cursor.execute("""
        SELECT TOP 1 id, event_description, event_date
        FROM docketwatch.dbo.case_events
        WHERE fk_cases = ? AND event_no = ?
        ORDER BY id DESC
    """, (fk_case, event_no))
    row = cursor.fetchone()
    if not row:
        return None, None
    case_event_id = row.id
    long_desc = row.event_description
    return case_event_id, long_desc

def sync_event_documents(cursor, fk_case: int, case_event_id: int):
    """
    Ensure documents exist and have target filenames and rel_path set.
    Creates missing document records from event_url if needed.
    Returns list of planned download dicts: {doc_uid, url, target_abs, rel_path}.
    """
    # First, get the event URL in case we need to create a document record
    cursor.execute("SELECT event_url FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
    event_row = cursor.fetchone()
    event_url = event_row.event_url if event_row and event_row.event_url else None
    
    # Look for existing documents linked to this event
    cursor.execute("""
        SELECT d.doc_uid, d.pdf_url, d.rel_path, d.doc_id
        FROM docketwatch.dbo.documents d
        WHERE d.fk_case = ? AND d.fk_case_event = ?
        ORDER BY d.doc_uid DESC
    """, (fk_case, case_event_id))
    docs = cursor.fetchall()

    log_message(cursor, fk_task_run, "INFO", f"Found {len(docs)} existing documents for event {case_event_id}", fk_case=fk_case)

    # If no documents exist and we have an event URL, create a document record
    if not docs and event_url:
        log_message(cursor, fk_task_run, "INFO", f"Creating document record for event URL: {event_url[:100]}...", fk_case=fk_case)
        
        # Extract doc_id from event URL if possible
        doc_id = extract_doc_id_from_url(event_url)
        if not doc_id:
            # Fallback: use event number as doc identifier
            cursor.execute("SELECT event_no FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
            event_no_row = cursor.fetchone()
            # Use zero-padded event number for proper PACER doc_id format
            if event_no_row and event_no_row.event_no:
                try:
                    doc_id = f"{int(event_no_row.event_no):08d}"
                except (ValueError, TypeError):
                    # If event_no is already a string or can't be converted, use it as-is
                    doc_id = str(event_no_row.event_no)
            else:
                doc_id = f"{case_event_id:08d}"

        # Get event description for proper pdf_title
        cursor.execute("SELECT event_description FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
        desc_row = cursor.fetchone()
        pdf_title = desc_row.event_description if desc_row and desc_row.event_description else "Docket Entry"

        # Create the document record
        doc_uid = str(uuid.uuid4())
        filename = f"E{doc_id}.pdf"
        rel_path = f"cases\\{fk_case}\\{filename}"
        
        cursor.execute("""
            INSERT INTO docketwatch.dbo.documents (
                doc_uid, fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Docket', 0, ?, GETDATE())
        """, (
            doc_uid, fk_case, case_event_id, PACER_TOOL_ID, doc_id, event_url, 
            pdf_title, rel_path
        ))
        cursor.commit()
        
        # Re-query to get the created document
        cursor.execute("""
            SELECT d.doc_uid, d.pdf_url, d.rel_path, d.doc_id
            FROM docketwatch.dbo.documents d
            WHERE d.doc_uid = ?
        """, (doc_uid,))
        docs = cursor.fetchall()
        
        log_message(cursor, fk_task_run, "INFO", f"Created document record with doc_uid: {doc_uid}", fk_case=fk_case)

    planned = []
    ensure_dir(os.path.join(PDF_ROOT, str(fk_case)))

    for d in docs:
        doc_uid = d.doc_uid
        pdf_url = getattr(d, "pdf_url", None) or event_url
        rel_path = getattr(d, "rel_path", None)
        doc_id = getattr(d, "doc_id", None)

        # Ensure we have a valid PDF URL
        if not pdf_url:
            log_message(cursor, fk_task_run, "WARNING", f"Document {doc_uid} has no PDF URL - skipping", fk_case=fk_case)
            continue

        # Generate rel_path if missing or pending
        if not rel_path or rel_path == 'pending':
            # Ensure we have a valid doc_id for proper filename
            if not doc_id:
                doc_id = extract_doc_id_from_url(pdf_url)
                if not doc_id:
                    # Get event_no for fallback doc_id
                    cursor.execute("SELECT event_no FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
                    event_no_row = cursor.fetchone()
                    if event_no_row and event_no_row.event_no:
                        try:
                            doc_id = f"{int(event_no_row.event_no):08d}"
                        except (ValueError, TypeError):
                            # If event_no is already a string or can't be converted, use it as-is
                            doc_id = str(event_no_row.event_no)
                    else:
                        doc_id = f"{case_event_id:08d}"
                
                # Update the doc_id in database
                cursor.execute("UPDATE docketwatch.dbo.documents SET doc_id = ? WHERE doc_uid = ?", (doc_id, doc_uid))
            
            # Create proper PACER filename convention: E{doc_id}.pdf
            file_name = f"E{doc_id}.pdf"
            rel_path = f"cases\\{fk_case}\\{file_name}"
            
            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET rel_path = ?
                WHERE doc_uid = ?
            """, (rel_path, doc_uid))
            cursor.commit()
            
            log_message(cursor, fk_task_run, "INFO", f"Updated rel_path for document {doc_uid}: {rel_path}", fk_case=fk_case)
        
        # Extract filename from rel_path
        file_name = os.path.basename(rel_path) if rel_path else f"doc_{doc_uid[:8]}.pdf"

        planned.append({
            "doc_uid": doc_uid,
            "url": pdf_url,
            "target_abs": os.path.join(PDF_ROOT, str(fk_case), file_name),
            "rel_path": rel_path
        })

    log_message(cursor, fk_task_run, "INFO", f"Prepared {len(planned)} documents for download", fk_case=fk_case)
    return planned

def download_and_mark_documents(cursor, planned_docs, fk_case: int):
    """Download documents with enhanced logging and error handling"""
    if not planned_docs:
        log_message(cursor, fk_task_run, "INFO", "No documents to download", fk_case=fk_case)
        return
    
    log_message(cursor, fk_task_run, "INFO", f"Starting download of {len(planned_docs)} document(s)", fk_case=fk_case)
    
    downloaded_count = 0
    failed_count = 0
    
    for i, p in enumerate(planned_docs, 1):
        doc_uid = p['doc_uid']
        url = p['url']
        target_path = p['target_abs']
        rel_path = p['rel_path']
        
        log_message(cursor, fk_task_run, "INFO", f"Downloading document {i}/{len(planned_docs)}: {doc_uid}", fk_case=fk_case)
        
        if not url:
            log_message(cursor, fk_task_run, "WARNING", f"Document {doc_uid} missing pdf_url - skipping", fk_case=fk_case)
            failed_count += 1
            continue
            
        # Check if file already exists and has reasonable size
        if os.path.exists(target_path):
            existing_size = os.path.getsize(target_path)
            if existing_size > 1000:  # More than 1KB, probably valid
                log_message(cursor, fk_task_run, "INFO", f"Document {doc_uid} already exists ({existing_size} bytes) - updating database", fk_case=fk_case)
                cursor.execute("""
                    UPDATE docketwatch.dbo.documents
                    SET file_size = ?, isfound = 1, rel_path = ?
                    WHERE doc_uid = ?
                """, (existing_size, rel_path, doc_uid))
                cursor.commit()
                downloaded_count += 1
                continue
        
        # Attempt download
        success, error_msg = download_pdf(url, target_path)
        
        if success:
            try:
                file_size = os.path.getsize(target_path)
                cursor.execute("""
                    UPDATE docketwatch.dbo.documents
                    SET file_size = ?, isfound = 1, rel_path = ?, date_downloaded = GETDATE()
                    WHERE doc_uid = ?
                """, (file_size, rel_path, doc_uid))
                cursor.commit()
                
                log_message(cursor, fk_task_run, "INFO", f"✓ Downloaded document {doc_uid} ({file_size:,} bytes) to {rel_path}", fk_case=fk_case)
                downloaded_count += 1
                
            except Exception as db_error:
                log_message(cursor, fk_task_run, "ERROR", f"Database update failed for {doc_uid}: {db_error}", fk_case=fk_case)
                failed_count += 1
        else:
            failed_count += 1
            error_msg_short = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
            log_message(cursor, fk_task_run, "ERROR", f"✗ Download failed for document {doc_uid}: {error_msg_short}", fk_case=fk_case)
            error_notifier.log_error("PDF download failed", 
                                   f"doc_uid={doc_uid}, url={url[:100]}..., error={error_msg}", 
                                   fk_task_run=fk_task_run, fk_case=fk_case)
    
    # Summary logging
    total = len(planned_docs)
    log_message(cursor, fk_task_run, "INFO", f"Document download summary: {downloaded_count}/{total} successful, {failed_count} failed", fk_case=fk_case)

# =========================
# Orchestrator for a single event
# =========================

def process_new_event(fk_case: int, event_no: int, court_code: str, cursor_arg=None, fk_task_run_arg=None):
    """
    Pipeline for a single new event:
      1) PACER scrape for this case
      2) Enrich event description and mark status
      3) Sync documents and download PDFs
      4) Trigger OCR discovery
      5) Trigger case summary
      6) Final status bump
    """
    # Use provided cursor/task_run or fall back to globals
    local_cursor = cursor_arg or cursor
    local_task_run = fk_task_run_arg or fk_task_run
    
    # Create a local connection if no cursor provided
    needs_local_connection = cursor_arg is None
    if needs_local_connection:
        try:
            import pyodbc
            local_conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
            local_conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            local_conn.setencoding(encoding='utf-8')
            local_cursor = local_conn.cursor()
            
            # Get or create task run
            script_filename = os.path.splitext(os.path.basename(__file__))[0]
            local_cursor.execute("""
                SELECT r.id as fk_task_run 
                FROM docketwatch.dbo.task_runs r
                INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
                WHERE s.filename = ? 
                ORDER BY r.id DESC
            """, (script_filename,))
            task_run = local_cursor.fetchone()
            local_task_run = task_run[0] if task_run else None
        except Exception as e:
            print(f"Warning: Could not create local database connection: {e}")
            return
    
    log_message(local_cursor, local_task_run, "INFO", f"Process start for fk_case={fk_case}, event_no={event_no}", fk_case=fk_case)

    scraped = refresh_case_via_pacer_scraper(fk_case)
    if not scraped:
        log_message(local_cursor, local_task_run, "WARNING", f"PACER scrape did not complete for fk_case={fk_case}", fk_case=fk_case)
    else:
        time.sleep(SCRAPER_COOLDOWN_SEC)

    case_event_id, long_desc = enrich_event_from_fresh_pacer(local_cursor, fk_case, event_no)
    if case_event_id:
        local_cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET stage_completed = 1
            WHERE id = ?
        """, (case_event_id,))
        if needs_local_connection:
            local_conn.commit()
        else:
            local_cursor.commit()
        if long_desc:
            log_message(local_cursor, local_task_run, "INFO", f"Updated long description for event {event_no}", fk_case=fk_case)

    if case_event_id:
        planned_docs = sync_event_documents(local_cursor, fk_case, case_event_id)
        if planned_docs:
            # For PACER documents, use the authenticated PDF downloader
            log_message(local_cursor, local_task_run, "INFO", f"Triggering authenticated PACER PDF download for case_event_id={case_event_id}", fk_case=fk_case)
            pdf_cmd = ["python", r"\\10.146.176.84\general\docketwatch\python\extract_pacer_pdf_file.py", str(case_event_id)]
            
            # Temporarily override globals for subprocess calls
            global cursor, fk_task_run
            try:
                original_cursor, original_task_run = cursor, fk_task_run
                cursor, fk_task_run = local_cursor, local_task_run
                pdf_result = run_subprocess(pdf_cmd, "PACER PDF download", fk_case=fk_case)
                # Restore original globals
                cursor, fk_task_run = original_cursor, original_task_run
            except NameError:
                # Globals don't exist yet, just use locals
                cursor, fk_task_run = local_cursor, local_task_run
                pdf_result = run_subprocess(pdf_cmd, "PACER PDF download", fk_case=fk_case)
            
            if pdf_result:
                log_message(local_cursor, local_task_run, "INFO", f"PACER PDF download completed successfully", fk_case=fk_case)
            else:
                log_message(local_cursor, local_task_run, "WARNING", f"PACER PDF download may not have completed successfully", fk_case=fk_case)
        else:
            log_message(local_cursor, local_task_run, "INFO", "No documents to download for this event", fk_case=fk_case)

    ok_ocr = trigger_ocr_discovery()
    time.sleep(OCR_SUMMARY_COOLDOWN_SEC)

    ok_sum = trigger_case_summary(fk_case)

    if case_event_id:
        final_stage = 5 if ok_sum else 4  # 5 = Summarized, 4 = OCR Complete
        local_cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET stage_completed = ?
            WHERE id = ?
        """, (final_stage, case_event_id))
        if needs_local_connection:
            local_conn.commit()
        else:
            local_cursor.commit()

    log_message(local_cursor, local_task_run, "INFO", f"Process end for fk_case={fk_case}, event_no={event_no}", fk_case=fk_case)
    
    # Clean up local connection if we created one
    if needs_local_connection:
        try:
            local_cursor.close()
            local_conn.close()
        except:
            pass
# =========================
# Tracked Cases + RSS Loop
# =========================

try:
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
        ORDER BY crt.court_code
    """)
    sites = cursor.fetchall()
    
    log_message(cursor, fk_task_run, "INFO", f"Processing {len(sites)} RSS feeds...")
    
    total_new_events = 0
    total_processed_items = 0
    failed_feeds = 0

    for site_idx, (court_code, base_url, url_suffix) in enumerate(sites, 1):
        rss_url = ""
        try:
            rss_url = base_url.rstrip("/") + (url_suffix or "/cgi-bin/rss_outside.pl")
            log_message(cursor, fk_task_run, "INFO", f"[{site_idx}/{len(sites)}] Checking RSS feed: {court_code} - {rss_url}")

            feed_start_time = time.time()
            
            try:
                response = requests.get(rss_url, timeout=20)
            except requests.exceptions.Timeout:
                msg = f"Timeout accessing RSS feed: {rss_url}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Timeout", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                failed_feeds += 1
                continue
            except requests.exceptions.RequestException as e:
                msg = f"Network error accessing RSS feed {rss_url}: {e}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Network Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                failed_feeds += 1
                continue

            if response.status_code != 200:
                msg = f"HTTP {response.status_code} from {rss_url}"
                log_message(cursor, fk_task_run, "WARNING", msg)
                if response.status_code >= 500:
                    error_notifier.log_error("RSS Feed Server Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                    failed_feeds += 1
                continue

            try:
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
            except Exception as e:
                msg = f"Failed to parse XML from RSS feed {rss_url}: {e}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Parse Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                failed_feeds += 1
                continue

            if not items:
                log_message(cursor, fk_task_run, "INFO", f"No entries in RSS feed for {court_code}")
            else:
                feed_duration = time.time() - feed_start_time
                log_message(cursor, fk_task_run, "INFO", f"Found {len(items)} entries in RSS feed for {court_code} (fetched in {feed_duration:.1f}s)")
                
            new_events_this_feed = 0

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

                # Filter out PACER "Unknown Document Type" error messages
                if event_description.lower().startswith('unknown document type'):
                    log_message(cursor, fk_task_run, "INFO", 
                                f"Skipping PACER unknown document type: {event_description}", 
                                fk_case=None)
                    continue  # Skip this RSS item - it's not actionable content

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

                # Insert case_event if not present (bulletproof PACER identifier check)
                if event_no != -1:
                    try:
                        # Extract PACER identifiers for bulletproof duplicate detection
                        pacer_doc_number, pacer_doc_id = extract_pacer_identifiers(event_description, event_url)
                        
                        print(f"[INFO] PACER IDs: doc_number={pacer_doc_number}, doc_id={pacer_doc_id}")
                        
                        # Bulletproof duplicate check using documents table
                        event_exists, existing_event_id = bulletproof_duplicate_check(
                            cursor, fk_case, pacer_doc_number, pacer_doc_id
                        )
                        
                        if event_exists:
                            print(f"[OK] Event already exists (ID: {existing_event_id}) - skipping PACER duplicate")
                            print(f"   PACER identifiers: doc_number={pacer_doc_number}, doc_id={pacer_doc_id}")
                        else:
                            # Event doesn't exist, create it
                            log_id = log_message(cursor, fk_task_run, "ALERT",
                                                 f"New RSS docket for {db_case_name} - Event No: {event_no}",
                                                 fk_case=fk_case)
                            cursor.execute("""
                                INSERT INTO docketwatch.dbo.case_events
                                  (event_date, event_no, event_description, fk_cases, stage_completed, fk_task_run_log, event_url)
                                VALUES (?, ?, ?, ?, 0, ?, ?)
                            """, (pub_date, event_no, event_description, fk_case, log_id, event_url))
                            print(f"[OK] Created new event {event_no} for {pub_date.date()}")
                            print(f"   PACER identifiers will be: doc_number={pacer_doc_number}, doc_id={pacer_doc_id}")

                            # Email alert and end-to-end pipeline for new events only
                            try:
                                send_docket_email(db_case_name, event_url, event_no, event_description)
                            except Exception:
                                # Non-fatal; already logged in send_docket_email
                                pass

                            try:
                                process_new_event(fk_case=fk_case, event_no=event_no, court_code=court_code)
                                new_events_this_feed += 1
                                total_new_events += 1
                            except Exception as e:
                                emsg = f"Pipeline error for fk_case={fk_case}, event_no={event_no}: {e}"
                                log_message(cursor, fk_task_run, "ERROR", emsg, fk_case=fk_case)
                                error_notifier.log_error("Pipeline error", emsg, fk_task_run=fk_task_run, fk_case=fk_case)

                        conn.commit()
                    except Exception as e:
                        print(f"[ERROR] Error handling event {event_no}: {e}")
                        conn.rollback()
                        raise
                else:
                    conn.commit()
                    log_message(cursor, fk_task_run, "WARNING",
                                f"RSS item missing event_no; recorded feed entry only for case {db_case_name}.",
                                fk_case=fk_case)
                
                total_processed_items += 1

            # Feed summary
            if new_events_this_feed > 0:
                log_message(cursor, fk_task_run, "ALERT", f"Feed {court_code} generated {new_events_this_feed} new event(s)")
            
        except Exception as e:
            msg = f"Unexpected error processing RSS feed {rss_url}: {safe_log_message(str(e))}"
            log_message(cursor, fk_task_run, "ERROR", msg)
            error_notifier.log_error("RSS Processing Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}, URL: {rss_url}")
            failed_feeds += 1
            continue

    # Overall summary
    success_feeds = len(sites) - failed_feeds
    log_message(cursor, fk_task_run, "INFO", f"RSS monitoring completed: {success_feeds}/{len(sites)} feeds successful, {total_new_events} new events detected, {total_processed_items} items processed")
    
    if total_new_events > 0:
        log_message(cursor, fk_task_run, "ALERT", f"[ALERT] RSS monitoring discovered {total_new_events} new court event(s) across {success_feeds} feeds")
    
    log_message(cursor, fk_task_run, "INFO", "RSS trigger script completed successfully.")

except Exception as e:
    error_msg = f"Critical script failure in main loop: {safe_log_message(str(e))}"
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
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)

print("\nScript finished.")
