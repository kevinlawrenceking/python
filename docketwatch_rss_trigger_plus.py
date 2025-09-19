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

# Add Selenium imports for PACER scraping
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

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

# PDF Download Scripts
ENHANCED_PDF_DOWNLOADER = r"\\10.146.176.84\general\docketwatch\python\enhanced_pacer_pdf_downloader.py"
COMBINED_PDF_PROCESSOR = r"\\10.146.176.84\general\docketwatch\python\combined_pacer_pdf_vprocessor.py"

# PACER Login Configuration
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
PACER_USERNAME = "docketwatch"  # You may want to store this in database
PACER_PASSWORD = "Tm123456!"   # You may want to store this in database

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

def trigger_enhanced_pdf_download(case_event_id: int):
    """Trigger the enhanced PDF downloader for a specific case event"""
    cmd = ["python", ENHANCED_PDF_DOWNLOADER, str(case_event_id)]
    return run_subprocess(cmd, "Enhanced PDF Download")

def trigger_combined_pdf_processor(case_event_id: int):
    """Trigger the combined PDF processor for a specific case event"""
    cmd = ["python", COMBINED_PDF_PROCESSOR, str(case_event_id)]
    return run_subprocess(cmd, "Combined PDF Processor")

# =========================
# PACER Login and Event Detail Scraping
# =========================

def create_chrome_driver():
    """Create a Chrome WebDriver instance with appropriate options"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    # Uncomment for headless mode (but may cause issues)
    # chrome_options.add_argument("--headless")
    
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def login_to_pacer(driver, court_url):
    """Login to PACER for a specific court"""
    try:
        login_url = court_url.rstrip("/") + "/cgi-bin/login.pl"
        log_message(cursor, fk_task_run, "INFO", f"Logging into PACER: {login_url}")
        
        driver.get(login_url)
        
        # Wait for login form and fill it out
        wait = WebDriverWait(driver, 15)
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "loginForm:loginName")))
        username_field.send_keys(PACER_USERNAME)
        
        password_field = driver.find_element(By.NAME, "loginForm:password")
        password_field.send_keys(PACER_PASSWORD)
        
        # Try to find and fill client code field if it exists
        try:
            client_code_field = driver.find_element(By.NAME, "loginForm:clientCode")
            client_code_field.send_keys("DocketWatch")
            log_message(cursor, fk_task_run, "INFO", "Client code 'DocketWatch' entered")
        except:
            log_message(cursor, fk_task_run, "INFO", "Client code field not found - skipping")
        
        # Submit login form
        login_button = driver.find_element(By.NAME, "loginForm:fbtnLogin")
        login_button.click()
        
        time.sleep(3)
        
        # Check if login was successful
        if "Invalid" in driver.page_source or "error" in driver.page_source.lower():
            log_message(cursor, fk_task_run, "ERROR", "PACER login failed - invalid credentials")
            return False
        
        log_message(cursor, fk_task_run, "INFO", "PACER login completed successfully")
        return True
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"PACER login error: {e}")
        return False

def scrape_event_details_from_pacer(cursor, fk_case: int, event_no: int, event_url: str):
    """
    Navigate to PACER event page and scrape full event description
    Returns the full event description text
    """
    driver = None
    try:
        log_message(cursor, fk_task_run, "INFO", f"Scraping event details for case {fk_case}, event {event_no}")
        
        # Get court URL from the case
        cursor.execute("""
            SELECT c.pacer_id, ct.pacer_url, c.case_name
            FROM docketwatch.dbo.cases c
            JOIN docketwatch.dbo.courts ct ON c.fk_court = ct.court_code
            WHERE c.id = ?
        """, (fk_case,))
        
        case_info = cursor.fetchone()
        if not case_info:
            log_message(cursor, fk_task_run, "ERROR", f"Could not find case info for fk_case {fk_case}")
            return None
        
        pacer_id, court_url, case_name = case_info
        
        if not court_url:
            log_message(cursor, fk_task_run, "WARNING", f"No court URL found for case {case_name}")
            return None
        
        # Create Chrome driver
        driver = create_chrome_driver()
        
        # Login to PACER
        if not login_to_pacer(driver, court_url):
            log_message(cursor, fk_task_run, "ERROR", f"Failed to login to PACER for case {case_name}")
            return None
        
        # Navigate to the event URL if provided, otherwise construct docket sheet URL
        if event_url and event_url.startswith("http"):
            target_url = event_url
        else:
            # Construct docket sheet URL
            target_url = f"{court_url.rstrip('/')}/cgi-bin/DktRpt.pl?{pacer_id}"
        
        log_message(cursor, fk_task_run, "INFO", f"Navigating to: {target_url}")
        driver.get(target_url)
        
        time.sleep(3)
        
        # Look for the specific event number on the docket sheet
        event_description = None
        
        # Try to find event description by looking for the event number
        try:
            # Look for table rows containing the event number
            event_links = driver.find_elements(By.XPATH, f"//a[contains(text(), '{event_no}')]")
            
            if event_links:
                # Click on the event link to get details
                event_link = event_links[0]
                event_link.click()
                time.sleep(2)
                
                # Look for event description in various possible locations
                description_selectors = [
                    "//td[contains(@class, 'docketText')]",
                    "//td[contains(text(), 'Description')]/../td[2]",
                    "//table//td[contains(text(), 'Event:')]/../td[2]",
                    "//div[contains(@class, 'eventDescription')]"
                ]
                
                for selector in description_selectors:
                    try:
                        desc_element = driver.find_element(By.XPATH, selector)
                        event_description = desc_element.text.strip()
                        if event_description and len(event_description) > 10:
                            break
                    except:
                        continue
            else:
                # If we can't find the specific event, try to get description from page source
                page_source = driver.page_source
                # Look for patterns that might contain the event description
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Find table rows and look for our event number
                for row in soup.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        # Check if any cell contains our event number
                        for i, cell in enumerate(cells):
                            if str(event_no) in cell.get_text():
                                # Try to get description from next cells
                                if i + 1 < len(cells):
                                    event_description = cells[i + 1].get_text().strip()
                                    if len(event_description) > 10:
                                        break
                        if event_description:
                            break
        
        except Exception as e:
            log_message(cursor, fk_task_run, "WARNING", f"Could not find specific event details: {e}")
            # Fallback: try to get any meaningful description from the page
            try:
                page_text = driver.page_source
                if f"Event {event_no}" in page_text or str(event_no) in page_text:
                    # Extract some context around the event number
                    import re
                    pattern = rf'.{{0,100}}{event_no}.{{0,200}}'
                    matches = re.findall(pattern, page_text, re.IGNORECASE | re.DOTALL)
                    if matches:
                        event_description = matches[0].strip()
                        # Clean up HTML tags
                        event_description = re.sub(r'<[^>]+>', '', event_description)
                        event_description = re.sub(r'\s+', ' ', event_description).strip()
            except:
                pass
        
        if event_description and len(event_description) > 10:
            log_message(cursor, fk_task_run, "INFO", f"Successfully scraped event description: {event_description[:100]}...")
            return event_description
        else:
            log_message(cursor, fk_task_run, "WARNING", f"Could not extract meaningful event description for event {event_no}")
            return None
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Error scraping event details: {e}")
        error_notifier.log_error("PACER Event Scraping Error", str(e), fk_task_run=fk_task_run, fk_case=fk_case)
        return None
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
# =========================
# Event and Document Enrichment
# =========================

def enrich_event_from_fresh_pacer(cursor, fk_case: int, event_no: int, event_url: str = None):
    """
    After the PACER scrape, pull the latest description for the event_no,
    then enhance it by scraping the full details from PACER directly.
    Returns (case_event_id, enhanced_description).
    """
    # First get the basic event info from our database
    cursor.execute("""
        SELECT TOP 1 id, event_description, event_date
        FROM docketwatch.dbo.case_events
        WHERE fk_cases = ? AND event_no = ?
        ORDER BY id DESC
    """, (fk_case, event_no))
    row = cursor.fetchone()
    if not row:
        log_message(cursor, fk_task_run, "WARNING", f"No case_event found for fk_case={fk_case}, event_no={event_no}")
        return None, None
    
    case_event_id = row.id
    current_desc = row.event_description or ""
    
    # Now scrape the full event description from PACER
    log_message(cursor, fk_task_run, "INFO", f"Enhancing event description for case_event_id {case_event_id}")
    
    enhanced_description = scrape_event_details_from_pacer(cursor, fk_case, event_no, event_url)
    
    if enhanced_description and enhanced_description != current_desc:
        # Update the database with the enhanced description
        try:
            cursor.execute("""
                UPDATE docketwatch.dbo.case_events
                SET event_description = ?, 
                    status = 'Enhanced from PACER',
                    last_updated = GETDATE()
                WHERE id = ?
            """, (enhanced_description, case_event_id))
            cursor.commit()
            
            log_message(cursor, fk_task_run, "INFO", 
                       f"Updated event_description for case_event_id {case_event_id} with enhanced PACER details")
            return case_event_id, enhanced_description
            
        except Exception as e:
            log_message(cursor, fk_task_run, "ERROR", f"Failed to update event_description: {e}")
            error_notifier.log_database_error(f"Failed to update case_event {case_event_id}: {e}", fk_task_run=fk_task_run)
            return case_event_id, current_desc
    else:
        if enhanced_description:
            log_message(cursor, fk_task_run, "INFO", f"Event description unchanged for case_event_id {case_event_id}")
        else:
            log_message(cursor, fk_task_run, "WARNING", f"Could not enhance event description for case_event_id {case_event_id}")
        return case_event_id, current_desc

def sync_event_documents(cursor, fk_case: int, case_event_id: int):
    """
    Ensure documents exist and have target filenames and rel_path set.
    Returns list of planned download dicts: {id, url, target_abs, rel_path}.
    """
    cursor.execute("""
        SELECT d.id, d.source_url, d.file_name, d.rel_path
        FROM docketwatch.dbo.documents d
        WHERE d.fk_case = ? AND (d.fk_case_event = ? OR d.fk_case_event IS NULL)
        ORDER BY d.id DESC
    """, (fk_case, case_event_id))
    docs = cursor.fetchall()

    planned = []
    ensure_dir(os.path.join(PDF_ROOT, str(fk_case)))

    for d in docs:
        doc_id = d.id
        source_url = getattr(d, "source_url", None)
        file_name = getattr(d, "file_name", None)
        rel_path = getattr(d, "rel_path", None)

        if not source_url:
            cursor.execute("SELECT event_url FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
            ev = cursor.fetchone()
            source_url = ev.event_url if ev and ev.event_url else None

        if not file_name:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            doc_hint = extract_doc_id_from_url(source_url) or f"doc{doc_id}"
            file_name = f"{ts}_{doc_hint}.pdf"
            rel_path = f"{fk_case}\\{file_name}"
            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET file_name = ?, rel_path = ?
                WHERE id = ?
            """, (file_name, rel_path, doc_id))
            cursor.commit()
        else:
            rel_path = f"{fk_case}\\{file_name}"

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
                SET file_size = ?, status = 'Downloaded', rel_path = ?
                WHERE id = ?
            """, (size, p["rel_path"], p["id"]))
            cursor.commit()
            log_message(cursor, fk_task_run, "INFO", f"Downloaded document {p['id']} to {p['rel_path']}", fk_case=fk_case)
        else:
            msg = f"Download failed for document {p['id']}: {err}"
            log_message(cursor, fk_task_run, "ERROR", msg, fk_case=fk_case)
            error_notifier.log_error("PDF download failed", f"doc_id={p['id']}, err={err}", fk_task_run=fk_task_run, fk_case=fk_case)

# =========================
# Orchestrator for a single event
# =========================

def process_new_event(fk_case: int, event_no: int, court_code: str, event_url: str = None):
    """
    Enhanced pipeline for a single new event:
      1) PACER scrape for this case
      2) Enrich event description with full PACER details
      3) Run enhanced PDF download scripts
      4) Sync documents and download PDFs
      5) Trigger OCR discovery
      6) Trigger case summary
      7) Final status update
    """
    log_message(cursor, fk_task_run, "INFO", f"Enhanced process start for fk_case={fk_case}, event_no={event_no}", fk_case=fk_case)

    # Step 1: Refresh case via PACER scraper
    scraped = refresh_case_via_pacer_scraper(fk_case)
    if not scraped:
        log_message(cursor, fk_task_run, "WARNING", f"PACER scrape did not complete for fk_case={fk_case}", fk_case=fk_case)
    else:
        time.sleep(SCRAPER_COOLDOWN_SEC)

    # Step 2: Enrich event description with full PACER details
    case_event_id, enhanced_desc = enrich_event_from_fresh_pacer(cursor, fk_case, event_no, event_url)
    if case_event_id:
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET status = 'Enhanced - Ready for PDF Processing'
            WHERE id = ?
        """, (case_event_id,))
        cursor.commit()
        
        if enhanced_desc:
            log_message(cursor, fk_task_run, "INFO", f"Enhanced event description for event {event_no}: {enhanced_desc[:100]}...", fk_case=fk_case)
    else:
        log_message(cursor, fk_task_run, "ERROR", f"Could not find or create case_event for fk_case={fk_case}, event_no={event_no}", fk_case=fk_case)
        return

    # Step 3: Run PDF download scripts
    if case_event_id:
        log_message(cursor, fk_task_run, "INFO", f"Starting PDF download process for case_event_id {case_event_id}", fk_case=fk_case)
        
        # Run Enhanced PDF Downloader
        pdf_download_success = trigger_enhanced_pdf_download(case_event_id)
        if pdf_download_success:
            log_message(cursor, fk_task_run, "INFO", f"Enhanced PDF download completed for case_event_id {case_event_id}", fk_case=fk_case)
        else:
            log_message(cursor, fk_task_run, "WARNING", f"Enhanced PDF download failed for case_event_id {case_event_id}", fk_case=fk_case)
        
        time.sleep(2)  # Brief pause between scripts
        
        # Run Combined PDF Processor
        pdf_process_success = trigger_combined_pdf_processor(case_event_id)
        if pdf_process_success:
            log_message(cursor, fk_task_run, "INFO", f"Combined PDF processor completed for case_event_id {case_event_id}", fk_case=fk_case)
        else:
            log_message(cursor, fk_task_run, "WARNING", f"Combined PDF processor failed for case_event_id {case_event_id}", fk_case=fk_case)

    # Step 4: Sync documents and download any remaining PDFs
    if case_event_id:
        planned_docs = sync_event_documents(cursor, fk_case, case_event_id)
        if planned_docs:
            download_and_mark_documents(cursor, planned_docs, fk_case)
            log_message(cursor, fk_task_run, "INFO", f"Downloaded {len(planned_docs)} additional documents", fk_case=fk_case)
        else:
            log_message(cursor, fk_task_run, "INFO", "No additional documents to download for this event", fk_case=fk_case)

    # Step 5: Trigger OCR discovery
    ok_ocr = trigger_ocr_discovery()
    if ok_ocr:
        log_message(cursor, fk_task_run, "INFO", "OCR discovery completed successfully", fk_case=fk_case)
    else:
        log_message(cursor, fk_task_run, "WARNING", "OCR discovery had issues", fk_case=fk_case)
    
    time.sleep(OCR_SUMMARY_COOLDOWN_SEC)

    # Step 6: Trigger case summary
    ok_sum = trigger_case_summary(fk_case)
    if ok_sum:
        log_message(cursor, fk_task_run, "INFO", "Case summary completed successfully", fk_case=fk_case)
    else:
        log_message(cursor, fk_task_run, "WARNING", "Case summary had issues", fk_case=fk_case)

    # Step 7: Final status update
    if case_event_id:
        final_status = "Completed - PDF & Summary Ready" if (ok_sum and (pdf_download_success or pdf_process_success)) else "Partial Processing Complete"
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET status = ?, last_updated = GETDATE()
            WHERE id = ?
        """, (final_status, case_event_id))
        cursor.commit()

    log_message(cursor, fk_task_run, "INFO", f"Enhanced process end for fk_case={fk_case}, event_no={event_no} - Status: {final_status}", fk_case=fk_case)
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
                            process_new_event(fk_case=fk_case, event_no=event_no, court_code=court_code, event_url=event_url)
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
