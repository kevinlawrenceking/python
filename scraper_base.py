# scraper_base.py
# Shared logic for all DocketWatch scraper scripts

import os
import sys
import re
import time
import uuid
import logging
import random
import string
import pyodbc
import requests
import smtplib
import unicodedata
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup

# Selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# OCR and PDF processing
import PyPDF2
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError

# AI summarization
import google.generativeai as genai
import markdown2

DEFAULT_CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

def send_case_update_alert(cursor, case_update_id):
    """
    Sends an HTML email alert for a case_update marked as storyworthy.
    Marks the update as emailed if successful.
    """
    # Load email config
    FROM_EMAIL = "it@tmz.com"
    TO_EMAILSx = [
        "Kevin.King@tmz.com",
        "Jennifer.Delgado@tmz.com",
        "Marlee.Goodman@tmz.com",
        "Priscilla.Hwang@tmz.com",
        "Shirley.Troche@tmz.com"
    ]
    TO_EMAILS = [
    "Kevin.King@tmz.com"
]
    SMTP_SERVER = "mx0a-00195501.pphosted.com"
    SMTP_PORT = 25
    INTERNAL_URL_BASE = "http://tmztools.tmz.local/court/docketwatch/case_details.cfm?id="

    # Pull update + case info
    cursor.execute("""
        SELECT u.id, u.fk_case, c.case_number, c.case_name, u.summary_tmz_html, u.summary_ap,
               u.created_at, c.case_url
        FROM docketwatch.dbo.case_updates u
        INNER JOIN docketwatch.dbo.cases c ON u.fk_case = c.id
        WHERE u.id = ?
    """, (case_update_id,))
    row = cursor.fetchone()
    if not row:
        logging.warning(f"Case update {case_update_id} not found.")
        return False

    (update_id, case_id, case_number, case_name,
     tmz_html, ap_summary, created_at, case_url) = row

    if not tmz_html or not ap_summary:
        logging.warning(f"Case update {update_id} is missing summaries.")
        return False

    internal_link = f"{INTERNAL_URL_BASE}{case_id}"

    # Build HTML
    html = f"<h2>TMZ Case Update: {case_number} – {case_name}</h2>"
    html += f"<p><b>Internal Link:</b> <a href='{internal_link}'>DocketWatch</a></p>"
    if case_url:
        html += f"<p><b>External Case Link:</b> <a href='{case_url}'>{case_url}</a></p>"
    html += "<hr>"
    html += f"<h3>Today's Legal Update Summary</h3><p>{ap_summary}</p>"
    html += tmz_html

    # Send email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Storyworthy Update: {case_number} – {case_name}"
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(TO_EMAILS)
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())

        cursor.execute("""
            UPDATE docketwatch.dbo.case_updates
            SET emailed = 1
            WHERE id = ?
        """, (case_update_id,))
        cursor.connection.commit()
        logging.info(f"Alert sent for case_update {case_update_id}")
        return True

    except Exception as e:
        logging.error(f"Failed to send alert for case_update {case_update_id}: {e}")
        return False
    
def generate_ai_summary_for_documents(cursor, case_event_id, docs_root_dir):
    """
    For all documents in a case_event with OCR but no summary, use Gemini to generate summaries.
    Updates summary_ai and summary_ai_html in the database.
    Returns the number of documents summarized.
    """
    # Load Gemini API key
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    key_row = cursor.fetchone()
    if not key_row or not key_row[0]:
        logging.warning("Gemini API key not found in dbo.utilities.")
        return 0
    gemini_key = key_row[0]
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-pro")

    # Get target documents
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.ocr_text,
            ISNULL(e.event_description, d.pdf_title) AS event_desc,
            CONVERT(char(10), ISNULL(e.event_date, d.date_downloaded), 23) AS event_date,
            c.summarize AS case_summary
        FROM docketwatch.dbo.documents d
        LEFT JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        JOIN docketwatch.dbo.cases c ON d.fk_case = c.id
        WHERE d.fk_case_event = ?
        AND d.ocr_text IS NOT NULL
        AND (d.summary_ai_html IS NULL OR LEN(d.summary_ai_html) < 10)
    """, (case_event_id,))
    rows = cursor.fetchall()
    if not rows:
        return 0

    INSTRUCTION = (
        "You are a legal summarizer. Write a concise, objective summary of the following legal document. "
        "Focus only on the content of the text. Use plain, neutral English. Do not write a headline, subhead, or story. "
        "Do not speculate or evaluate. Just summarize the filing."
    )

    summarized = 0

    for doc_uid, ocr_text, event_desc, event_date, case_summary in rows:
        if not ocr_text or len(ocr_text.strip()) < 100:
            continue

        # Construct context-aware prompt
        context = f"""
{INSTRUCTION}

--- CASE CONTEXT ---
{case_summary or '[No case summary provided]'}

--- EVENT ---
Date: {event_date}
Description: {event_desc}

--- DOCUMENT TEXT ---
{ocr_text.strip()[:10000]}
"""
        try:
            response = model.generate_content(context[:16000])
            text_output = response.text.strip()
            html_output = markdown2.markdown(text_output)

            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET summary_ai = ?, summary_ai_html = ?, ai_processed_at = GETDATE()
                WHERE doc_uid = ?
            """, (text_output, html_output, doc_uid))
            cursor.connection.commit()
            summarized += 1
        except Exception as e:
            logging.warning(f"[Gemini] Summary failed for doc_uid {doc_uid}: {e}")

    return summarized


def summarize_case_update_old(cursor, case_update_id):
    """
    Summarizes the full case_update using Gemini.
    Returns (summary_ap, summary_tmz_html, is_storyworthy).
    """
    # 1. Load Gemini API key
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    if not row or not row[0]:
        logging.warning("Gemini API key not found in dbo.utilities.")
        return None, None, False
    genai.configure(api_key=row[0])
    model = genai.GenerativeModel("gemini-2.5-pro")

    # 2. Load all documents for the case_update
    cursor.execute("""
        SELECT d.summary_ai, d.summary_ai_html, d.pdf_title, d.ocr_text
        FROM docketwatch.dbo.documents d
        INNER JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        WHERE e.fk_case_update = ?
        ORDER BY d.date_downloaded ASC
    """, (case_update_id,))
    docs = cursor.fetchall()
    if not docs:
        logging.warning(f"No documents found for case_update {case_update_id}")
        return None, None, False

    # 3. Load case info
    cursor.execute("""
        SELECT c.id, c.case_number, c.case_name, c.summarize
        FROM docketwatch.dbo.case_updates u
        INNER JOIN docketwatch.dbo.cases c ON u.fk_case = c.id
        WHERE u.id = ?
    """, (case_update_id,))
    case_row = cursor.fetchone()
    if not case_row:
        return None, None, False

    case_id, case_number, case_name, case_summary = case_row

    # 4. Build event and document context
    combined_summary_texts = []
    for summary, _, title, _ in docs:
        if summary:
            combined_summary_texts.append(f"Title: {title or '(Untitled)'}\n{summary.strip()}")
    full_text = "\n\n".join(combined_summary_texts)

    # 5. Gemini AP prompt
    ap_prompt = f"""
You are an Associated Press journalist. Write a concise, factual bulletin based on the following case update.
Use plain language. Do not exaggerate or add speculation.
Only report on what happened in the new documents.

CASE: {case_name} ({case_number})
SUMMARY CONTEXT:
{case_summary or '[No summary]'}

DOCUMENT SUMMARIES:
{full_text[:9000]}
"""

    # 6. Gemini TMZ-style prompt
    tmz_prompt = f"""
You are writing a story for TMZ. Be punchy, dramatic, and focused on the celebrity or legal angle.
Use this format:

Headline: [Short, clicky headline]
Body: <p>[Single HTML paragraph, 50–100 words]</p>

CASE: {case_name} ({case_number})
DOCUMENT SUMMARIES:
{full_text[:9000]}
"""

    try:
        ap_response = model.generate_content(ap_prompt)
        ap_summary = ap_response.text.strip()

        tmz_response = model.generate_content(tmz_prompt)
        tmz_raw = tmz_response.text.strip()

        # Format TMZ output
        headline = body = None
        if "Headline:" in tmz_raw and "Body:" in tmz_raw:
            headline = tmz_raw.split("Headline:")[1].split("Body:")[0].strip()
            body = tmz_raw.split("Body:")[1].strip()
            if not body.startswith("<p>"):
                body = f"<p>{body}</p>"
        else:
            headline = "Case Update"
            body = f"<p>{tmz_raw}</p>"

        tmz_html = f"<h4>{headline}</h4>\n{body}"
        is_storyworthy = "No Story Necessary" not in headline

        # Save back to DB
        cursor.execute("""
            UPDATE docketwatch.dbo.case_updates
            SET summary_ap = ?, summary_tmz_html = ?, reviewed_at = GETDATE(),
                summarized_by = 'gemini', is_storyworthy = ?
            WHERE id = ?
        """, (ap_summary, tmz_html, int(is_storyworthy), case_update_id))
        cursor.connection.commit()

        return ap_summary, tmz_html, is_storyworthy

    except Exception as e:
        logging.error(f"Gemini failed on case_update {case_update_id}: {e}")
        return None, None, False


def create_case_update_if_needed(cursor, case_id):
    """
    Creates a new case_update if any unassigned, unemailed case_events exist.
    Assigns those events to the new case_update and returns the update ID + event IDs.
    """
    # 1. Find unemailed, unassigned events for this case
    cursor.execute("""
        SELECT id
        FROM docketwatch.dbo.case_events
        WHERE fk_cases = ? AND emailed = 0 AND fk_case_update IS NULL
        ORDER BY created_at ASC
    """, (case_id,))
    rows = cursor.fetchall()
    if not rows:
        return None, []

    event_ids = [row.id for row in rows]

    # 2. Create new case_update
    update_id = str(uuid.uuid4())
    now = datetime.now()

    cursor.execute("""
        INSERT INTO docketwatch.dbo.case_updates (
            id, fk_case, created_at
        ) VALUES (?, ?, ?)
    """, (update_id, case_id, now))

    # 3. Assign each event to this case_update
    for event_id in event_ids:
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET fk_case_update = ?
            WHERE id = ?
        """, (update_id, event_id))

    cursor.connection.commit()
    return update_id, event_ids


# === Email/Logging Setup ===
FROM_EMAIL = "it@tmz.com"
ALERT_EMAILS = [
    "kevin.king@tmz.com"
]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

# === Logging ===
def setup_logging(log_path):
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")

def init_logging_and_filename():
    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    log_path = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
    setup_logging(log_path)
    logging.info(f"=== Script {script_filename} started ===")
    return script_filename

# === DB Connection ===
def get_db_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    return conn, conn.cursor()

# === Logging Utility ===
def log_message(cursor, fk_task_run, log_type, message, fk_case=None):
    logging.info(message)
    if not cursor or not fk_task_run:
        return None
    try:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.task_runs_log (
                fk_task_run, log_timestamp, log_type, description, fk_case
            )
            OUTPUT INSERTED.id 
            VALUES (?, GETDATE(), ?, ?, ?)
        """, (fk_task_run, log_type, message, fk_case))
        log_id = cursor.fetchone()[0]
        cursor.connection.commit()
        return log_id
    except Exception as ex:
        logging.warning(f"Failed to write to task_runs_log: {ex}")
        return None

# === Not Found Case Alerting ===
def send_not_found_email(case_id, fail_count, level, last_checked=None):
    subject = f"DocketWatch {level}: Case ID {case_id} Not Found"
    body = f"""
    <html>
    <body>
        <p>Case ID <strong>{case_id}</strong> was not found.</p>
        <p>Failure Count: {fail_count}</p>
        {"<p>Last Checked: " + str(last_checked) + "</p>" if last_checked else ""}
    </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(ALERT_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, ALERT_EMAILS, msg.as_string())
    except Exception as e:
        logging.error(f"Failed to send not-found email for case {case_id}: {e}")

import random

def insert_documents_for_event(cursor, case_event_id, tool_id=2):
    cursor.execute("""
        SELECT COUNT(*) 
        FROM docketwatch.dbo.documents 
        WHERE fk_case_event = ?
    """, (case_event_id,))
    if cursor.fetchone()[0] > 0:
        return 0  # already has documents

    # Generate a fake but unique doc_id based on timestamp and randomness
    cursor.execute("SELECT GETDATE()")
    timestamp = cursor.fetchone()[0]
    unique_doc_id = int(timestamp.timestamp() * 1000) + random.randint(1, 999)

    cursor.execute("""
        INSERT INTO docketwatch.dbo.documents (
            fk_case_event, fk_tool, pdf_title, rel_path, pdf_type, pdf_no, doc_id, date_downloaded
        ) VALUES (?, ?, 'Placeholder PDF Title', 'pending', 'Docket', 0, ?, GETDATE())
    """, (case_event_id, tool_id, unique_doc_id))
    cursor.connection.commit()
    return 1


def mark_case_not_found(cursor, case_id, fk_task_run=None, threshold=3):
    """
    Increments the not_found_count and sets not_found_flag when threshold is hit.
    Also updates last_not_found timestamp. Sends an email to kevin.king@tmz.com.
    Logs an alert if threshold reached, otherwise logs a warning.

    Args:
        cursor: pyodbc cursor object
        case_id: The ID of the case to flag
        fk_task_run: Optional. Used for logging.
        threshold: How many failures before flag is set (default 3)
    """
    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET 
            not_found_count = ISNULL(not_found_count, 0) + 1,
            last_not_found = GETDATE(),
            not_found_flag = CASE 
                                WHEN ISNULL(not_found_count, 0) + 1 >= ? THEN 1
                                ELSE 0
                             END
        WHERE id = ?
    """, (threshold, case_id))
    cursor.connection.commit()

    # Check if threshold reached for alerting
    cursor.execute("SELECT not_found_count, last_not_found FROM docketwatch.dbo.cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    count = row[0]
    last_checked = row[1]

    if count >= threshold:
        level = "ALERT"
        log_message(cursor, fk_task_run, "ALERT", f"Case ID {case_id} could not be found {count} times and is now flagged as not found.", fk_case=case_id)
        send_not_found_email(case_id, count, level, last_checked)
    else:
        level = "WARNING"
        log_message(cursor, fk_task_run, "WARNING", f"Case ID {case_id} was not found (failure count: {count}).", fk_case=case_id)

# === Tool/Task/Selectors Utilities ===

def get_task_context_by_tool_id(cursor, tool_id):
    cursor.execute("""
        SELECT TOP 1 
            r.id, 
            t.id as tool_id, 
            t.search_url, 
            t.isLogin, 
            t.login_url,
            t.username, 
            t.pass, 
            s.filename, 
            s.filename + '.log' as logfile_name,
            t.username_selector,
            t.password_selector,
            t.search_button_selector,
            t.login_checkbox,
            t.login_button_selector 
        FROM docketwatch.dbo.tools t
        LEFT JOIN docketwatch.dbo.scheduled_task s ON s.fk_tool = t.id
        LEFT JOIN docketwatch.dbo.task_runs r ON r.fk_scheduled_task = s.id
        WHERE t.id = ?
        ORDER BY r.id DESC
    """, (tool_id,))

    row = cursor.fetchone()
    return {
        "fk_task_run": row[0] if row else None,
        "tool_id": row[1] if row else None,
        "search_url": row[2] if row else None,
        "is_login": bool(row[3]) if row else False,
        "login_url": row[4] if row else None,
        "username": row[5] if row else None,
        "pass": row[6] if row else None,
        "filename": row[7] if row else None,
        "logfile_name": row[8] if row else "docketwatch_scraper.log",
        "username_selector": row[9] if row else None,
        "password_selector": row[10] if row else None,
        "search_button_selector": row[11] if row else None,
        "login_checkbox": row[12] if row else None,
        "login_button_selector": row[13] if row else None
    } if row else None

def mark_case_found(cursor, case_id):
    """
    Resets not_found_count, not_found_flag, last_not_found when a previously not found case is now found.
    Updates last_found to current timestamp.
    """
    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET
            not_found_count = 0,
            not_found_flag = 0,
            last_not_found = NULL,
            last_found = GETDATE()
        WHERE id = ?
    """, (case_id,))
    cursor.connection.commit()

def update_case_records(cursor, case_id, case_number, case_name, TOOL_ID, fk_court, case_type, fk_task_run, current_url):
    # Update master case record
    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET
            case_number = ?,
            case_name = ?,
            fk_tool = ?,
            status = 'Tracked',
            fk_court = ?,
            case_type = ?,
            fk_task_run_log = ?,
            last_updated = GETDATE()
        WHERE id = ?
    """, (case_number, case_name, TOOL_ID, fk_court, case_type, fk_task_run, case_id))
    # Update tool-specific case record
    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET
            fk_tool = ?,
            case_number = ?,
            case_name = ?,
            case_url = ?,
            is_tracked = 1,
            last_updated = GETDATE(),
            fk_task_run_log = ?
        WHERE id = ?
    """, (TOOL_ID, case_number, case_name, current_url, fk_task_run, case_id))
    cursor.connection.commit()
    log_message(cursor, fk_task_run, "INFO", f"Updated case {case_number} ({case_name}).", fk_case=case_id)

def insert_new_case_events(cursor, fk_case, events, fk_task_run):
    inserted = 0
    for event_date, description, extra in events:
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_description = ? AND event_date = ?
        """, (fk_case, description, event_date))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_events (
                    fk_cases, event_date, event_description,
                    additional_information, fk_task_run_log
                )
                VALUES (?, ?, ?, ?, ?)
            """, (fk_case, event_date, description, extra, fk_task_run))
            inserted += 1
    cursor.connection.commit()
    log_type = "ALERT" if inserted > 0 else "INFO"
    log_message(cursor, fk_task_run, log_type, f"Inserted {inserted} new event(s) for case ID {fk_case}", fk_case=fk_case)
    return inserted

def extract_case_name_from_html(page_source, case_name_selector=None):
    try:
        if not case_name_selector:
            return None  # skip if selector is not set
        soup = BeautifulSoup(page_source, "html.parser")
        element = soup.select_one(case_name_selector)
        if element:
            return element.get_text(strip=True)
        else:
            logging.info(f"Case name element not found using selector: {case_name_selector}")
    except Exception as e:
        logging.warning(f"Failed to extract case name using selector '{case_name_selector}': {e}")
    return None  # fallback if not found or error

def extract_court_and_type(soup, fk_county, cursor):
    import logging
    court_name = ""
    case_type = ""
    fk_court = None

    court_span = soup.find("span", {"id": "liCRCourtLocation"}) or soup.find("span", {"id": "liCourtLocationNotCR"})
    if court_span:
        court_name = court_span.get_text(strip=True)
        cursor.execute("""
            SELECT court_code FROM docketwatch.dbo.courts
            WHERE fk_county = ? AND court_name = ?
        """, (fk_county, court_name))
        result = cursor.fetchone()
        if result:
            fk_court = result[0]
        else:
            logging.warning(f"[NO MATCH] Court not found in DB: '{court_name}' (fk_county: {fk_county}) — skipping insert.")

    type_span = soup.find("span", {"id": "liCaseType"})
    if type_span:
        case_type = type_span.get_text(strip=True)

    return fk_court, case_type


def perform_tool_login(driver, context):
    log_message(None, context["fk_task_run"], "INFO", f"Performing login for tool {context['tool_id']}")

    try:
        driver.get(context["login_url"])

        # Wait for and fill in username
        username_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, context["username_selector"]))
        )
        username_input.clear()
        username_input.send_keys(context["username"])

        # Wait for and fill in password
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, context["password_selector"]))
        )
        password_input.clear()
        password_input.send_keys(context["pass"])

        # Click TOS checkbox if required
        if context.get("login_checkbox"):
            try:
                checkbox = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, context["login_checkbox"]))
                )
                if not checkbox.is_selected():
                    checkbox.click()
                log_message(None, context["fk_task_run"], "INFO", "TOS checkbox clicked.")
                time.sleep(0.5)
            except Exception as e:
                log_message(None, context["fk_task_run"], "WARNING", f"Failed to click TOS checkbox: {e}")

        # Wait for and click the login button
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, context["login_button_selector"]))
        ).click()

        log_message(None, context["fk_task_run"], "INFO", "Login attempt completed.")
        time.sleep(3)

    except Exception as e:
        log_message(None, context["fk_task_run"], "ERROR", f"Login failed: {e}")
        raise

def download_pending_documents_for_event(cursor, case_event_id):
    """
    Downloads all documents for the given case_event that have rel_path = 'pending'.
    Returns the number of PDFs successfully marked as downloaded.
    """
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.doc_id,
            c.id AS fk_case,
            ps.url + '/cgi-bin/show_multidocs.pl?caseid=' + 
                CAST(c.pacer_id AS VARCHAR) +
                '&arr_de_seq_nums=' + CAST(e.arr_de_seq_nums AS VARCHAR) +
                '&pdf_header=2&pdf_toggle_possible=1&zipit=1' AS download_url
        FROM docketwatch.dbo.documents d
        INNER JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
        INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
        WHERE d.fk_case_event = ? AND d.rel_path = 'pending'
    """, (case_event_id,))
    rows = cursor.fetchall()
    if not rows:
        return 0

    FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"
    inserted = 0

    for row in rows:
        doc_id = row.doc_id
        doc_uid = row.doc_uid
        fk_case = row.fk_case
        download_url = row.download_url
        filename = f"E{doc_id}.pdf"
        case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
        os.makedirs(case_dir, exist_ok=True)
        dest_path = os.path.join(case_dir, filename)

        # Simulate download
        with open(dest_path, "wb") as f:
            f.write(b"%PDF-1.4\n% placeholder content")  # Replace with real download logic later

        rel_path = f"cases\\{fk_case}\\{filename}"
        cursor.execute("""
            UPDATE docketwatch.dbo.documents
            SET rel_path = ?, date_downloaded = GETDATE()
            WHERE doc_uid = ?
        """, (rel_path, doc_uid))
        cursor.connection.commit()
        inserted += 1

    return inserted

def get_tool_selectors(cursor, tool_id):
    cursor.execute("""
        SELECT 
            search_url,
            case_number_input,
            search_button_selector,
            result_row_selector,
            case_link_selector,
            case_name_selector,
            court_name_selector,
            case_type_selector,
            events_table_selector,
            event_col_0_label,
            event_col_1_label,
            event_col_2_label,
            events_column_count,
            pre_search_click_selector,
            captcha_type,
            fk_county
        FROM docketwatch.dbo.tools
        WHERE id = ?
    """, (tool_id,))
    row = cursor.fetchone()
    if not row:
        return {}

    keys = [desc[0] for desc in cursor.description]
    return dict(zip(keys, row))

# === Common Utility: Solve 2Captcha reCAPTCHA ===

def solve_recaptcha_2captcha(api_key, site_key, page_url):
    import requests
    import time

    logging.info("Sending CAPTCHA to 2Captcha...")

    payload = {
        'key': api_key,
        'method': 'userrecaptcha',
        'googlekey': site_key,
        'pageurl': page_url,
        'json': 1
    }
    response = requests.post("http://2captcha.com/in.php", data=payload).json()
    if response.get("status") != 1:
        logging.error("2Captcha request failed: " + response.get("request", ""))
        raise Exception("2Captcha request failed: " + response.get("request", ""))

    captcha_id = response["request"]
    logging.info(f"2Captcha request accepted. ID: {captcha_id}")

    for attempt in range(20):
        time.sleep(3)
        check = requests.get(f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1").json()
        if check.get("status") == 1:
            logging.info("CAPTCHA solution received.")
            return check["request"]
        logging.info(f"Waiting for CAPTCHA solution... attempt {attempt + 1}")

    logging.error("2Captcha timeout waiting for solution")
    raise Exception("2Captcha timeout waiting for solution")

# === PACER Billing Extraction (Current Table Format) ===

def extract_and_store_pacer_billing(soup, cursor, fk_case, fk_task_run=None):
    try:
        billing_table = None
        for table in soup.find_all("table"):
            # Find table with "PACER Service Center" in header
            if table.find("font", string=re.compile("PACER Service Center")):
                billing_table = table
                break

        if not billing_table:
            log_message(cursor, fk_task_run, "INFO", "No PACER billing table found.")
            return False

        rows = billing_table.find_all("tr")
        data = {}
        billing_reference = None

        # Parse the transaction date/time
        for row in rows:
            if row.find("font", color="DARKBLUE") and row.find("td", align="CENTER"):
                date_font = row.find("font", color="DARKBLUE")
                billing_reference = date_font.get_text(strip=True)
                log_message(cursor, fk_task_run, "INFO", f"Billing reference (datetime): {billing_reference}")

        # Now parse all data in <th>/<td> pairs (across and down)
        for row in rows:
            cells = row.find_all(['th', 'td'])
            i = 0
            while i < len(cells) - 1:
                label = cells[i].get_text(strip=True).replace(":", "")
                value = cells[i+1].get_text(strip=True)
                if label:
                    data[label] = value
                    log_message(cursor, fk_task_run, "DEBUG", f"Parsed billing data: {label} = {value}")
                i += 2

        # log_message(cursor, fk_task_run, "DEBUG", f"Parsed billing data dictionary: {data}")

        pages = int(data.get("Billable Pages", "0") or "0")
        cost = float((data.get("Cost", "0.00") or "0.00").replace('$', '').replace(',', ''))
        description = data.get("Description", None)
        pacer_login = data.get("PACER Login", None)
        client_code = data.get("Client Code", "DocketWatch")
        search_criteria = data.get("Search Criteria", None)

        cursor.execute("""
            INSERT INTO docketwatch.dbo.pacer_billing_history (
                fk_case, created_at, billing_reference, pages, cost, 
                description, pacer_login, client_code, search_criteria
            )
            VALUES (?, GETDATE(), ?, ?, ?, ?, ?, ?, ?)
        """, (
            fk_case, billing_reference, pages, cost,
            description, pacer_login, client_code, search_criteria
        ))
        cursor.connection.commit()

        log_message(cursor, fk_task_run, "INFO", f"PACER billing: {pages} pages / ${cost:.2f} – {description}")
        return True

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Failed to extract PACER billing data: {e}")
        return False
    
    def preprocess_image(img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 5, 75, 75)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return bw

def generate_ai_summary_for_documents_older(cursor, case_event_id, docs_root_dir):
    """
    For all documents in a case_event with OCR but no summary, use Gemini to generate summaries.
    Updates summary_ai and summary_ai_html in the database.
    Returns the number of documents summarized.
    """
    # Load Gemini API key
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    key_row = cursor.fetchone()
    if not key_row or not key_row[0]:
        logging.warning("Gemini API key not found in dbo.utilities.")
        return 0
    gemini_key = key_row[0]
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-pro")

    # Get target documents
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.ocr_text,
            ISNULL(e.event_description, d.pdf_title) AS event_desc,
            CONVERT(char(10), ISNULL(e.event_date, d.date_downloaded), 23) AS event_date,
            c.summarize AS case_summary
        FROM docketwatch.dbo.documents d
        LEFT JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        JOIN docketwatch.dbo.cases c ON d.fk_case = c.id
        WHERE d.fk_case_event = ?
        AND d.ocr_text IS NOT NULL
        AND (d.summary_ai_html IS NULL OR LEN(d.summary_ai_html) < 10)
    """, (case_event_id,))
    rows = cursor.fetchall()
    if not rows:
        return 0

    RULES = """
SYSTEM: You are an experienced legal journalist. Your task is to analyze the following court document and produce a concise, neutral summary for a general audience.

Your analysis must adhere to these rules:
- Source Material: Base your summary only on the content of the provided document. Do not infer or include external information.
- Case Context: You will be provided with a short case summary to help anchor your understanding. However, your analysis must still focus exclusively on the content of the current document.
- Tone: Use plain, accessible English. Remain objective and avoid speculation. Write as if for an internal newsroom memo, not for public publication.
- Constraint: Do not describe the general case status or procedural history unless a specific, new event (like a scheduled hearing date or recent ruling) is explicitly mentioned in this document.

Follow this output format precisely:

### EVENT SUMMARY
Summarize the core filing, argument, or ruling in under 150 words.

### NEWSWORTHINESS
- Purpose: Evaluate whether the content of this specific document alone justifies its own story.
- Output:  
  Yes - <reason in 15 words or less>  
  OR  
  No - <reason in 15 words or less>

### STORY
- If NEWSWORTHINESS is "No":
  - HEADLINE: No Story Necessary.
  - SUBHEAD:
  - BODY:
- If NEWSWORTHINESS is "Yes":
  - HEADLINE: <A Title-Case Headline in 15 Words or Less>
  - SUBHEAD: <A descriptive sentence-case subhead in 25 words or less>
  - BODY: <A 250–400 word article using the markdown headings below>

### KEY DETAILS
Write the key facts in this section. Do not include instructions or placeholder text.

### WHAT'S NEXT
List any next steps or dates found in the document. Do not include instructions or placeholder text.

Only return the finished article — do not echo this prompt.
"""

    summarized = 0

    for doc_uid, ocr_text, event_desc, event_date, case_summary in rows:
        if not ocr_text or len(ocr_text.strip()) < 100:
            continue

        # Build prompt
        case_summary = (case_summary or "")[:2000]
        body_text = f"Date: {event_date}\nDescription: {event_desc}\n\n{ocr_text}"
        if len(body_text) > 10000:
            body_text = body_text[:8000] + "\n...\n" + body_text[-2000:]

        full_prompt = RULES.replace("{CASE_OVERVIEW}", case_summary).replace("{PDF_BODY}", body_text)

        try:
            response = model.generate_content(full_prompt[:16000])
            text_output = response.text.strip()
            html_output = markdown2.markdown(text_output)

            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET summary_ai = ?, summary_ai_html = ?, ai_processed_at = GETDATE()
                WHERE doc_uid = ?
            """, (text_output, html_output, doc_uid))
            cursor.connection.commit()
            summarized += 1
        except Exception as e:
            logging.warning(f"Gemini failed for doc_uid {doc_uid}: {e}")

    return summarized

def clean_ocr_text(txt):
    txt = re.sub(r'^Page \d+\s*\n', '', txt, flags=re.MULTILINE)
    txt = re.sub(r'-\n(?=\w)', '', txt)
    txt = re.sub(r'(?<!\n)\n(?!\n)', ' ', txt)
    txt = re.sub(r' +', ' ', txt)
    return unicodedata.normalize('NFKD', txt.strip())



# === OCR Utilities ===
def is_valid_pdf(file_path):
    try:
        with open(file_path, 'rb') as f:
            return f.read(5) == b'%PDF-'
    except Exception:
        return False

def preprocess_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, d=5, sigmaColor=75, sigmaSpace=75)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = thresh.shape[:2]
    M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
    return cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def clean_ocr_text(text: str) -> str:
    text = re.sub(r'^[A-Z ]+ v\.? [A-Z ]+\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^Page \d+\s*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\s*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'-\n(?=\w)', '', text)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r' +', ' ', text)
    text = text.replace('“', '"').replace('”', '"').replace('–', '-')
    return text.strip()

# === OCR Execution ===
def perform_ocr_for_documents(cursor, case_event_id, docs_root_dir):
    """
    For all documents in this case_event that have no OCR text, run OCR and update the DB.
    Returns the number of OCRs performed.
    """
    cursor.execute("""
        SELECT doc_uid, rel_path
        FROM docketwatch.dbo.documents
        WHERE fk_case_event = ? AND (ocr_text IS NULL OR LEN(ocr_text) < 10)
        AND rel_path IS NOT NULL AND rel_path NOT IN ('pending', '')
    """, (case_event_id,))
    rows = cursor.fetchall()
    if not rows:
        return 0

    count = 0
    for doc_uid, rel_path in rows:
        abs_path = os.path.join(docs_root_dir, rel_path)
        if not os.path.isfile(abs_path):
            log_message(cursor, None, "ERROR", f"File not found: {abs_path}")
            continue

        if not is_valid_pdf(abs_path):
            log_message(cursor, None, "ERROR", f"Invalid PDF header: {abs_path}")
            continue

        text = ""

        # Try extracting embedded text layer
        try:
            with open(abs_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for pg in reader.pages:
                    text += (pg.extract_text() or "") + "\n"
        except Exception as e:
            log_message(cursor, None, "WARNING", f"Failed to extract embedded text for {rel_path}: {e}")
            text = ""

        # Run OCR if text layer is weak
        if len(text.strip()) < 200:
            try:
                images = convert_from_path(abs_path, dpi=300, poppler_path=r"C:\\Poppler\\bin")
                for pil in images:
                    img = preprocess_image(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
                    text += pytesseract.image_to_string(img, config="--oem 1 --psm 6") + "\n"
            except PDFPageCountError as e:
                log_message(cursor, None, "ERROR", f"Unreadable PDF (PDFPageCountError): {rel_path} — {e}")
                continue
            except Exception as e:
                log_message(cursor, None, "ERROR", f"OCR failed on {rel_path}: {e}")
                continue

        clean_text_result = clean_ocr_text(text)
        if len(clean_text_result.strip()) < 100:
            log_message(cursor, None, "INFO", f"OCR text too short, skipping DB update for {rel_path}")
            continue

        try:
            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET ocr_text = ?, ai_processed_at = ?
                WHERE doc_uid = ?
            """, (clean_text_result, datetime.now(), doc_uid))
            cursor.connection.commit()
            count += 1
        except Exception as e:
            log_message(cursor, None, "ERROR", f"Failed to update OCR text for {rel_path}: {e}")

    return count