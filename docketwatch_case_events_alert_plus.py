import pyodbc
import google.generativeai as genai
import logging
import os
import sys
import json
import re  # <--- CRITICAL FIX: Added missing import for regular expressions
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# --- Logging Setup ---
script_dir = os.path.dirname(os.path.abspath(__file__))
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_DIR = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"{script_filename}.log")

logger = logging.getLogger(__name__)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Set DEBUG level for everything
logger.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)
console_handler.setLevel(logging.DEBUG)


# --- Constants ---
FROM_EMAIL = "it@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25
INTERNAL_URL_BASE = "http://tmztools.tmz.local/court/docketwatch/case_details.cfm?id="

conn = None
cursor = None

def get_db_connection():
    """Establishes and returns a database connection and cursor."""
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
    """Ensures that the owners listed for a case's tool are in the email recipient list."""
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
            cursor.execute("SELECT 1 FROM docketwatch.dbo.case_email_recipients WHERE fk_case = ? AND fk_username = ?", (case_id, username))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO docketwatch.dbo.case_email_recipients (fk_case, fk_username) VALUES (?, ?)", (case_id, username))
                logger.info(f"Added {username} to case_email_recipients for case {case_id}")
            else:
                logger.debug(f"{username} already exists in case_email_recipients for case {case_id}.")
        else:
            logger.warning(f"User '{username}' from tool owners not found in docketwatch.dbo.users. Skipping.")

def get_email_recipients(cursor, case_id):
    """Retrieves a list of unique email addresses for a given case."""
    cursor.execute("""
        SELECT u.email
        FROM docketwatch.dbo.case_email_recipients r
        INNER JOIN docketwatch.dbo.users u ON r.fk_username = u.username
        WHERE r.fk_case = ?
    """, (case_id,))
    emails = {row.email for row in cursor.fetchall() if row.email}
    return list(emails)

def get_gemini_key(cursor):
    """Retrieves the Gemini API key from the database."""
    try:
        cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    except pyodbc.Error as ex:
        logger.error(f"Database error retrieving Gemini API key: {ex}")
        return None

def get_case_celebrities(cursor, case_id):
    """Retrieves a comma-separated string of celebrity names for a case."""
    cursor.execute("""
        SELECT e.name as celebrity_name
        FROM docketwatch.dbo.cases c
        INNER JOIN docketwatch.dbo.case_celebrity_matches m ON m.fk_case = c.id
        INNER JOIN docketwatch.dbo.celebrities e ON e.id = m.fk_celebrity
        WHERE c.id = ?
    """, (case_id,))
    rows = cursor.fetchall()
    return ", ".join([r.celebrity_name for r in rows])

# --- Gemini Model Configuration ---

GEMINI_MODEL_NAME = "gemini-2.5-pro"

def generate_summaries(cursor, case_number, case_name, today_updates, backstory_events, article_refs, celebrities_text):
    """
    Generates two distinct summaries of a legal case using the Gemini API:
    1. A formal, AP-style news bulletin.
    2. A punchy, TMZ-style HTML summary.
    """
    base_info = f"""
### CASE INFORMATION ###
Case Number: {case_number}
Case Name: {case_name}
Celebrities Involved: {celebrities_text or 'Not Specified'}

### TODAY'S FILINGS (Primary Focus) ###
{today_updates or 'No new filings today.'}

### HISTORICAL CONTEXT (Backstory) ###
{backstory_events or 'No historical context provided.'}

### RELATED NEWS (External Context) ###
{article_refs or 'No related articles provided.'}
"""
    ap_prompt = f"""
You are an expert journalist for the Associated Press (AP). Your task is to write a concise, factual, and neutral news bulletin based on the provided legal case information.
CRITICAL INSTRUCTIONS:
1.  **Focus primarily on "TODAY'S FILINGS".** Use the historical and news context only to add clarity to today's events.
2.  **Start with a dateline.** Use the format 'CITY, State (AP) --'. Since you don't know the city, use 'LOS ANGELES (AP) --'.
3.  **Output should be a single, well-formed paragraph.**
4.  **Do NOT add any headlines, titles, or conversational text.**
5.  Maintain a professional, third-person perspective. Avoid hype or sensationalism.
Use the information below to write your bulletin:
{base_info}
"""
    tmz_prompt = f"""
You are a top writer for an entertainment news website like TMZ. Your style must be punchy, engaging, and slightly sensational, focusing on the celebrity angle.
CRITICAL INSTRUCTIONS:
1.  **You MUST format your response with a 'Headline:' and a 'Body:' on separate lines.**
2.  The Headline should be attention-grabbing and less than 10 words.
3.  The Body must be a **single HTML paragraph** fully enclosed in `<p>` and `</p>` tags.
4.  Focus on the most dramatic or celebrity-relevant aspect of "TODAY'S FILINGS".
5.  DO NOT include any other text, explanation, or markdown.
Example of the REQUIRED format:
Headline: John Doe's Legal Battle Heats Up in Court
Body: <p>Actor John Doe made a dramatic appearance in court today as his multi-million dollar lawsuit against his former manager took another explosive turn. Sources say the tension was palpable as new evidence was presented...</p>
Now, write your summary based on this information:
{base_info}
"""
    try:
        gemini_api_key = get_gemini_key(cursor)
        if not gemini_api_key:
            # CRITICAL FIX: Use the configured logger instance
            logger.error("Gemini API key not found in dbo.utilities. Cannot generate summaries.")
            return None, None

        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)

        ap_generation_config = {"temperature": 0.5, "max_output_tokens": 400}
        logger.debug(f"Gemini AP Prompt for {case_number}:\n{ap_prompt}")
        ap_response = model.generate_content(ap_prompt, generation_config=ap_generation_config)
        ap_summary = ap_response.text.strip()

        tmz_generation_config = {"temperature": 0.7, "max_output_tokens": 400}
        logger.debug(f"Gemini TMZ Prompt for {case_number}:\n{tmz_prompt}")
        tmz_response = model.generate_content(tmz_prompt, generation_config=tmz_generation_config)
        tmz_raw_output = tmz_response.text.strip()

        tmz_html = None
        match = re.search(r"Headline:(.*)\s*Body:(.*)", tmz_raw_output, re.DOTALL | re.IGNORECASE)

        if match:
            headline = match.group(1).strip()
            body = match.group(2).strip()
            if not body.startswith('<p>'):
                body = f'<p>{body}</p>'
            tmz_html = f"<h4>{headline}</h4>\n{body}"
        else:
            logger.warning(f"Gemini failed to follow TMZ format for case {case_number}. Raw output: '{tmz_raw_output}'")
            tmz_html = f"<h4>Summary for {case_name}</h4>\n<p>{tmz_raw_output}</p>"

        return ap_summary, tmz_html

    except Exception as e:
        logger.exception(f"Error during Gemini summary generation for case {case_number}: {e}")
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
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while sending email: {e}")

def main(case_id):
    """Main execution function for processing a single case."""
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

        # --- Fetch Unemailed Events ---
        cursor.execute("""
            SELECT c.case_number, c.case_name, e.event_date, e.event_description, e.id
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE c.id = ? AND e.emailed = 0
            ORDER BY e.created_at DESC
        """, (case_id,))
        today_events = cursor.fetchall()
        logger.debug(f"Found {len(today_events)} unemailed event(s) for case {case_id}")

        if not today_events:
            logger.info(f"No new, un-emailed case events found for case {case_id}.")
            return

        for i, row in enumerate(today_events):
            logger.debug(f"today_event[{i}] = id:{row.id}, date:{row.event_date}, desc:{row.event_description}")

        # --- Diagnostic: Log All Events Regardless of emailed Status ---
        cursor.execute("""
            SELECT c.case_number, c.case_name, e.event_date, e.event_description, e.id, e.emailed
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE c.id = ?
            ORDER BY e.created_at DESC
        """, (case_id,))
        all_events = cursor.fetchall()
        logger.debug(f"All events for case {case_id} (regardless of emailed status):")
        for i, row in enumerate(all_events):
            logger.debug(f"all_event[{i}] = id:{row.id}, emailed:{row.emailed}, date:{row.event_date}, desc:{row.event_description}")

        # --- Build Update Strings ---
        case_number = today_events[0].case_number
        case_name = today_events[0].case_name
        today_updates = "\n".join([
            f"{row.event_date.strftime('%Y-%m-%d')} - {row.event_description}"
            for row in today_events if isinstance(row.event_date, datetime)
        ])
        logger.debug(f"today_updates string for Gemini:\n{today_updates}")

        cursor.execute("""
            SELECT TOP 10 event_date, event_description
            FROM docketwatch.dbo.case_events
            WHERE fk_cases = ?
            ORDER BY event_date DESC
        """, (case_id,))
        backstory = cursor.fetchall()
        backstory_events = "\n".join([
            f"{row.event_date.strftime('%Y-%m-%d')} - {row.event_description}"
            for row in backstory if isinstance(row.event_date, datetime)
        ])
        logger.debug(f"backstory_events string:\n{backstory_events}")

        cursor.execute("""
            SELECT case_url AS url, title, description, image_url, datePublished
            FROM docketwatch.dbo.case_links
            WHERE fk_case = ?
            ORDER BY datePublished DESC
        """, (case_id,))
        articles = cursor.fetchall()
        article_refs = "\n".join([
            f"{row.title} – {row.url}\n{row.description}"
            for row in articles
        ])
        logger.debug(f"article_refs string:\n{article_refs}")

        celebrities_text = get_case_celebrities(cursor, case_id)
        logger.debug(f"celebrities_text: {celebrities_text}")

        # --- Generate Summaries ---
        ap_summary, tmz_html = generate_summaries(
            cursor,
            case_number,
            case_name,
            today_updates,
            backstory_events,
            article_refs,
            celebrities_text
        )

        if not ap_summary or not tmz_html:
            logger.error(f"Failed to generate summaries for case {case_id}. Aborting email process.")
            return

        # --- Prepare Email ---
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

        logger.debug(f"Final HTML email body for case {case_id}:\n{html}")

        # --- Force Only Kevin For Now ---
        recipients = ["kevin.king@tmz.com"]
        send_email(f"Breaking Case Update: {case_number}", html, recipients)

        # --- Mark Events as Emailed ---
        event_ids_to_update = [row.id for row in today_events]
        for event_id in event_ids_to_update:
            cursor.execute("""
                UPDATE docketwatch.dbo.case_events
                SET summarize = ?, tmz_summarize = ?, emailed = 1
                WHERE id = ?
            """, (ap_summary, tmz_html, event_id))
        conn.commit()
        logger.info(f"Marked {len(event_ids_to_update)} events as emailed for case {case_id}")

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
    logger.info(f"[Startup] Script triggered with args: {sys.argv}")
    if len(sys.argv) != 2:
        logger.error("Usage: python docketwatch_case_events_alert_plus.py <case_id>")
        sys.exit(1)

    try:
        case_id_arg = int(sys.argv[1])
        logger.info(f"Starting case event alert for case_id {case_id_arg}...")
        main(case_id_arg)
    except ValueError:
        logger.error("Invalid case_id provided. Please provide a numeric case_id.")
        sys.exit(1)
