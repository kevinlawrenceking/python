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
  - Gemini case-level summary generation

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
SCRAPER_SCRIPT = r"\\10.146.176.84\general\docketwatch\python\docketwatch_scraper.py"
PDF_ROOT = r"\\10.146.176.84\general\docketwatch\cases"
OCR_TRIGGER = r"\\10.146.176.84\general\docketwatch\python\final_pdfs_finder.py"
SUMMARIZER = r"\\10.146.176.84\general\docketwatch\python\pacer_case_event_pdf_summarizer.py"

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

def download_pdf(url, local_path):
    try:
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True, None
    except Exception as e:
        return False, str(e)

def refresh_case_via_pacer_scraper(fk_case: int):
    cmd = ["python", SCRAPER_SCRIPT, str(PACER_TOOL_ID), str(fk_case)]
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
    Returns list of planned download dicts: {id, url, target_abs, rel_path}.
    """
    cursor.execute("""
        SELECT d.doc_uid, d.pdf_url, d.rel_path, d.doc_id
        FROM docketwatch.dbo.documents d
        WHERE d.fk_case = ? AND d.fk_case_event = ?
        ORDER BY d.doc_uid DESC
    """, (fk_case, case_event_id))
    docs = cursor.fetchall()

    planned = []
    ensure_dir(os.path.join(PDF_ROOT, str(fk_case)))

    for d in docs:
        doc_id = d.doc_uid  # Use doc_uid as the unique identifier
        source_url = getattr(d, "pdf_url", None)  # Use pdf_url instead of source_url
        rel_path = getattr(d, "rel_path", None)

        if not source_url:
            cursor.execute("SELECT event_url FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
            ev = cursor.fetchone()
            source_url = ev.event_url if ev and ev.event_url else None

        # Generate filename from doc_id if rel_path is pending
        if rel_path == 'pending' or not rel_path:
            doc_hint = extract_doc_id_from_url(source_url) or f"doc{doc_id}"
            file_name = f"E{d.doc_id}.pdf" if d.doc_id else f"{doc_hint}.pdf"
            rel_path = f"cases\\{fk_case}\\{file_name}"

        planned.append({
            "id": doc_id,
            "url": source_url,
            "target_abs": os.path.join(PDF_ROOT, str(fk_case), file_name),
            "rel_path": rel_path
        })

    return planned

def download_and_mark_documents(cursor, planned_docs, fk_case: int):
    for p in planned_docs:
        if not p["url"]:
            log_message(cursor, fk_task_run, "WARNING", f"Document {p['id']} missing source_url", fk_case=fk_case)
            continue
        ok, err = download_pdf(p["url"], p["target_abs"])
        if ok:
            try:
                size = os.path.getsize(p["target_abs"])
            except Exception:
                size = None
            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET rel_path = ?, date_downloaded = GETDATE()
                WHERE doc_uid = ?
            """, (p["rel_path"], p["id"]))
            cursor.commit()
            log_message(cursor, fk_task_run, "INFO", f"Downloaded document {p['id']} to {p['rel_path']}", fk_case=fk_case)
        else:
            msg = f"Download failed for document {p['id']}: {err}"
            log_message(cursor, fk_task_run, "ERROR", msg, fk_case=fk_case)
            error_notifier.log_error("PDF download failed", f"doc_id={p['id']}, err={err}", fk_task_run=fk_task_run, fk_case=fk_case)

# =========================
# Orchestrator for a single event
# =========================

def process_new_event(fk_case: int, event_no: int, court_code: str):
    """
    Pipeline for a single new event:
      1) PACER scrape for this case
      2) Enrich event description and mark status
      3) Sync documents and download PDFs
      4) Trigger OCR discovery
      5) Trigger case summary
      6) Final status bump
    """
    log_message(cursor, fk_task_run, "INFO", f"Process start for fk_case={fk_case}, event_no={event_no}", fk_case=fk_case)

    scraped = refresh_case_via_pacer_scraper(fk_case)
    if not scraped:
        log_message(cursor, fk_task_run, "WARNING", f"PACER scrape did not complete for fk_case={fk_case}", fk_case=fk_case)
    else:
        time.sleep(SCRAPER_COOLDOWN_SEC)

    case_event_id, long_desc = enrich_event_from_fresh_pacer(cursor, fk_case, event_no)
    if case_event_id:
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET status = 'Pending OCR'
            WHERE id = ?
        """, (case_event_id,))
        cursor.commit()
        if long_desc:
            log_message(cursor, fk_task_run, "INFO", f"Updated long description for event {event_no}", fk_case=fk_case)

    if case_event_id:
        planned_docs = sync_event_documents(cursor, fk_case, case_event_id)
        if planned_docs:
            download_and_mark_documents(cursor, planned_docs, fk_case)
        else:
            log_message(cursor, fk_task_run, "INFO", "No documents to download for this event", fk_case=fk_case)

    ok_ocr = trigger_ocr_discovery()
    time.sleep(OCR_SUMMARY_COOLDOWN_SEC)

    ok_sum = trigger_case_summary(fk_case)

    if case_event_id:
        final_status = "Summarized" if ok_sum else "Pending Summary"
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET status = ?
            WHERE id = ?
        """, (final_status, case_event_id))
        cursor.commit()

    log_message(cursor, fk_task_run, "INFO", f"Process end for fk_case={fk_case}, event_no={event_no}", fk_case=fk_case)
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
                error_notifier.log_error("RSS Feed Timeout", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue
            except requests.exceptions.RequestException as e:
                msg = f"Network error accessing RSS feed {rss_url}: {e}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Network Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue

            if response.status_code != 200:
                msg = f"HTTP {response.status_code} from {rss_url}"
                log_message(cursor, fk_task_run, "WARNING", msg)
                if response.status_code >= 500:
                    error_notifier.log_error("RSS Feed Server Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
                continue

            try:
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
            except Exception as e:
                msg = f"Failed to parse XML from RSS feed {rss_url}: {e}"
                log_message(cursor, fk_task_run, "ERROR", msg)
                error_notifier.log_error("RSS Feed Parse Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}")
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
                            VALUES (?, ?, ?, ?, 'RSS Pending', ?, ?)
                        """, (pub_date, event_no, event_description, fk_case, log_id, event_url))

                        conn.commit()

                        # Email alert and end-to-end pipeline
                        try:
                            send_docket_email(db_case_name, event_url, event_no, event_description)
                        except Exception:
                            # Non-fatal; already logged in send_docket_email
                            pass

                        try:
                            process_new_event(fk_case=fk_case, event_no=event_no, court_code=court_code)
                        except Exception as e:
                            emsg = f"Pipeline error for fk_case={fk_case}, event_no={event_no}: {e}"
                            log_message(cursor, fk_task_run, "ERROR", emsg, fk_case=fk_case)
                            error_notifier.log_error("Pipeline error", emsg, fk_task_run=fk_task_run, fk_case=fk_case)
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
            error_notifier.log_error("RSS Processing Error", msg, fk_task_run=fk_task_run, additional_context=f"Court: {court_code}, URL: {rss_url}")
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
        error_notifier.log_database_error(error_msg, fk_task_run=fk_task_run)

print("\nScript finished.")
