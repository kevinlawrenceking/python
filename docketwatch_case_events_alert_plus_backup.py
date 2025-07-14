import pyodbc
import google.generativeai as genai  # Renamed for clarity as per standard practice
import logging
import os
import sys
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import requests  # <--- ADDED: Import the requests library

# --- Logging Setup ---
script_dir = os.path.dirname(os.path.abspath(__file__))
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_DIR = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"{script_filename}.log")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logging.getLogger('pyodbc').setLevel(logging.WARNING)

# --- Constants ---
FROM_EMAIL = "it@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25
INTERNAL_URL_BASE = "http://tmztools.tmz.local/court/docketwatch/case_details.cfm?id="

conn = None
cursor = None

def get_db_connection():
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        logger.info("Database connection successful.")
        return conn, cursor
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        logger.error(f"Database connection failed: {sqlstate}")
        raise

def ensure_case_email_recipients(cursor, case_id):
    cursor.execute("""
        SELECT t.owners
        FROM docketwatch.dbo.cases c
        INNER JOIN docketwatch.dbo.tools t ON c.fk_tool = t.id
        WHERE c.id = ?
    """, (case_id,))
    row = cursor.fetchone()
    if not row or not row.owners:
        logger.info(f"No owners found or empty owners for case {case_id}.")
        return
    try:
        owners = json.loads(row.owners)
        if not isinstance(owners, list):
            logger.warning(f"Tool owners for case {case_id} is not a JSON array. Skipping.")
            return
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in tool owners for case {case_id}: {e}")
        return
    except Exception as e:
        logger.warning(f"Unexpected error parsing tool owners for case {case_id}: {e}")
        return

    for username in owners:
        username = str(username).strip()
        if not username:
            continue
        cursor.execute("SELECT username FROM docketwatch.dbo.users WHERE username = ?", (username,))
        if cursor.fetchone():
            cursor.execute("""
                SELECT 1 FROM docketwatch.dbo.case_email_recipients
                WHERE fk_case = ? AND fk_username = ?
            """, (case_id, username))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.case_email_recipients (fk_case, fk_username)
                    VALUES (?, ?)
                """, (case_id, username))
                logger.info(f"Added {username} to case_email_recipients for case {case_id}")
            else:
                logger.debug(f"{username} already exists in case_email_recipients for case {case_id}.")
        else:
            logger.warning(f"User '{username}' from tool owners not found in docketwatch.dbo.users. Skipping.")
def get_email_recipients(cursor, case_id):
    cursor.execute("""
        SELECT u.email
        FROM docketwatch.dbo.case_email_recipients r
        INNER JOIN docketwatch.dbo.users u ON r.fk_username = u.username
        WHERE r.fk_case = ?  
    """, (case_id,))
    emails = {row.email for row in cursor.fetchall() if row.email}
    return list(emails)

def get_gemini_key(cursor):
    try:
        cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    except pyodbc.Error as ex:
        logger.error(f"Database error retrieving Gemini API key: {ex}")
        return None

def get_case_celebrities(cursor, case_id):
    cursor.execute("""
        SELECT e.name as celebrity_name
        FROM docketwatch.dbo.cases c
        INNER JOIN docketwatch.dbo.case_celebrity_matches m ON m.fk_case = c.id
        INNER JOIN docketwatch.dbo.celebrities e ON e.id = m.fk_celebrity
        WHERE c.id = ?
    """, (case_id,))
    rows = cursor.fetchall()
    return ", ".join([r.celebrity_name for r in rows])

def generate_summaries(cursor, case_number, case_name, today_updates, backstory_events, article_refs, celebrities_text):
    base_info = f"""CASE INFORMATION
Case Number: {case_number}
Case Name: {case_name}
Celebrities Involved: {celebrities_text or 'None'}

TODAY'S FILINGS:
{today_updates or 'None'}

PAST EVENTS (Context Only):
{backstory_events or 'None'}

RELATED TMZ ARTICLES:
{article_refs or 'None'}
"""

    ap_prompt = f"""You are an AP wire reporter. Write a clear, factual, brief news bulletin. Avoid hype, avoid editorializing. Just the facts.
Based on the following information, write a one-paragraph AP-style news update titled 'Today's Summary of Events'.

{base_info}
"""

    tmz_prompt = f"""You are writing for an entertainment news site like TMZ or Variety. Format your response with:

Headline: A punchy, attention-grabbing title  
Body: One short paragraph in HTML

Example:
Celebrity Drama in Court Over Millions  
<p>In a surprising court turn, actor John Doe appeared today in a civil suit alleging...</p>

Now write your summary based on:
{base_info}
"""

    try:
        gemini_api_key = get_gemini_key(cursor)
        if not gemini_api_key:
            logger.error("Gemini API key missing.")
            return None, None

        genai.configure(api_key=gemini_api_key)
        model_name = 'gemini-2.0-flash'
        ap_response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"contents": [{"role": "user", "parts": [{"text": ap_prompt}]}], "generationConfig": {"temperature": 0.6, "max_output_tokens": 400}})
        )
        ap_data = ap_response.json()
        ap_summary = ap_data["candidates"][0]["content"]["parts"][0]["text"].strip() if ap_data.get("candidates") else ""

        tmz_response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"contents": [{"role": "user", "parts": [{"text": tmz_prompt}]}], "generationConfig": {"temperature": 0.7, "max_output_tokens": 400}})
        )
        tmz_data = tmz_response.json()
        tmz_summary_raw = tmz_data["candidates"][0]["content"]["parts"][0]["text"].strip() if tmz_data.get("candidates") else ""

        if tmz_summary_raw and "\n" in tmz_summary_raw:
            headline, body = tmz_summary_raw.split("\n", 1)
            headline = headline.strip().replace('<h4>', '').replace('</h4>', '')
            tmz_html = f"<h4>{headline}</h4>\n{body.strip()}"
        else:
            tmz_html = tmz_summary_raw.strip()

        return ap_summary, tmz_html
    except Exception as e:
        logger.exception(f"Error during summary generation: {e}")
        return None, None

def send_email(subject, body, recipients):
    """Sends an HTML email to a list of recipients."""
    if not recipients:
        logger.warning("Send email called with no recipients.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(recipients) 
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
        logger.info(f"Email sent successfully to {', '.join(recipients)}")
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP connection error: {e}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication error: {e}")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while sending email: {e}")

def main(case_id):
    global conn, cursor
    try:
        conn, cursor = get_db_connection()
    except Exception:
        sys.exit(1)

    try:
        ensure_case_email_recipients(cursor, case_id)
        conn.commit()

        recipients = get_email_recipients(cursor, case_id)
        if not recipients:
            logger.info(f"No recipients found for case {case_id}. Email not sent.")
            return

        cursor.execute("""
            SELECT 
                c.case_number,
                c.case_name,
                e.event_date,
                e.event_description,
                e.id
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE c.id = ? AND e.emailed = 0
            ORDER BY e.created_at DESC
        """, (case_id,))
        today_events = cursor.fetchall()

        if not today_events:
            logger.info(f"No new, un-emailed case events found for case {case_id}.")
            return

        case_number = today_events[0].case_number
        case_name = today_events[0].case_name
        today_updates = "\n".join([
            f"{row.event_date.strftime('%Y-%m-%d')} - {row.event_description}" 
            for row in today_events
            if isinstance(row.event_date, datetime)
        ])

        cursor.execute("""
            SELECT TOP 10 event_date, event_description
            FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? 
            ORDER BY event_date DESC
        """, (case_id,))
        backstory = cursor.fetchall()
        backstory_events = "\n".join([
            f"{row.event_date.strftime('%Y-%m-%d')} - {row.event_description}" 
            for row in backstory
            if isinstance(row.event_date, datetime)
        ])

        cursor.execute("""
            SELECT case_url AS url, title, description, image_url, datePublished
            FROM docketwatch.dbo.case_links
            WHERE fk_case = ?
            ORDER BY datePublished DESC
        """, (case_id,))
        articles = cursor.fetchall()
        article_refs = "\n".join([f"{row.title} – {row.url}\n{row.description}" for row in articles])

        celebrities_text = get_case_celebrities(cursor, case_id)
        celebrity_line = f"Celebrities involved: {celebrities_text}" if celebrities_text else ""

        ap_summary, tmz_html = generate_summaries(cursor, case_number, case_name, today_updates, backstory_events, article_refs, celebrity_line)

        if not ap_summary or not tmz_html:
            logger.error(f"Failed to generate summaries for case {case_id}. Aborting email process.")
            return

        event_ids_to_update = [row.id for row in today_events]
        for event_id in event_ids_to_update:
            cursor.execute("""
                UPDATE docketwatch.dbo.case_events
                SET summarize = ?, tmz_summarize = ?, emailed = 1
                WHERE id = ?
            """, (ap_summary, tmz_html, event_id))
        conn.commit()
        logger.info(f"Updated {len(event_ids_to_update)} events for case {case_id} with summaries and set emailed=1.")
        internal_url = f"{INTERNAL_URL_BASE}{case_id}"
        html = f"<h3>TMZ Case Update: {case_number} – {case_name}</h3>"
        if celebrities_text:
            html += f"<p><b>Celebrities involved:</b> {celebrities_text}</p>"
        html += f"<p><b>Internal Link:</b> <a href='{internal_url}'>DocketWatch</a></p>"
        html += f"<h4>Today's Summary of Events</h4><p>{ap_summary}</p>"
        html += tmz_html
        html += "<h4>Today's Filings:</h4><ul>"
        for row in today_events:
            event_date_str = row.event_date.strftime('%Y-%m-%d') if isinstance(row.event_date, datetime) else "N/A"
            html += f"<li>{event_date_str} – {row.event_description}</li>"
        html += "</ul>"

        send_email(f"Breaking Case Update: {case_number}", html, recipients)
        logger.info(f"Process finished for case {case_id}.")

    except Exception as e:
        logger.exception(f"An unhandled error occurred during main execution for case {case_id}: {e}")
    finally:
        if cursor:
            cursor.close()
            logger.info("Database cursor closed.")
        if conn:
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python your_script_name.py <case_id>")
        print("Usage: python your_script_name.py <case_id>")
        sys.exit(1)
    
    try:
        case_id_arg = int(sys.argv[1])
        logger.info(f"Starting case event alert for case_id {case_id_arg}...")
        print(f"Starting case event alert for case_id {case_id_arg}...")
        main(case_id_arg)
        print("Process finished.")
    except ValueError:
        logger.error("Invalid case_id provided. Please provide a numeric case_id.")
        print("Invalid case_id. Please provide a numeric case_id.")
        sys.exit(1)
