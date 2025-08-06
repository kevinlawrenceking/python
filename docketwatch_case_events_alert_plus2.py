import pyodbc
import logging
import os
import sys
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from bs4 import BeautifulSoup
from error_notification_system import create_error_notifier

# Setup logging
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# === Initialize error notification system ===
error_notifier = create_error_notifier(script_filename)

log_dir = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, f"{script_filename}.log")
logging.basicConfig(filename=log_path, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Config
FROM_EMAIL = "it@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25
INTERNAL_URL_BASE = "http://docketwatch.tmz.local/court/docketwatch/case_details.cfm?id="
DOCS_BASE_URL = "http://docketwatch.tmz.local/docs/cases"
EMAIL_RECIPIENTS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "marlee.chartash@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]


def get_db_connection():
    """Get database connection with proper encoding handling."""
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        # Try to handle encoding issues by using different settings
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8', errors='replace')
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8', errors='replace') 
        conn.setencoding(encoding='utf-8', errors='replace')
        return conn, conn.cursor()
    except Exception as e:
        error_msg = f"Failed to connect to database: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg)
        raise


def clean_text(text):
    """Clean text to handle encoding issues and garbage characters."""
    if not text:
        return text
    
    # Convert to string if not already
    text = str(text)
    
    # Replace common problematic characters
    replacements = {
        '\x92': "'",  # Right single quotation mark
        '\x93': '"',  # Left double quotation mark  
        '\x94': '"',  # Right double quotation mark
        '\x96': '–',  # En dash
        '\x97': '—',  # Em dash
        '\xbf': '?',  # Inverted question mark or invalid char
        '\x91': "'",  # Left single quotation mark
        '\x95': '•',  # Bullet point
        '\xa0': ' ',  # Non-breaking space
    }
    
    for old_char, new_char in replacements.items():
        text = text.replace(old_char, new_char)
    
    # Remove any remaining non-printable characters except newlines and tabs
    cleaned = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    
    return cleaned


def get_case_details(cursor, case_id):
    """Get case details with proper error handling for encoding issues."""
    try:
        cursor.execute("""
            SELECT c.id, c.case_number, c.case_name, c.summarize_html, c.case_url
            FROM docketwatch.dbo.cases c
            WHERE c.id = ?
        """, (case_id,))
        row = cursor.fetchone()
        
        if row:
            # Clean all text fields to handle encoding issues
            cleaned_row = (
                row.id,
                clean_text(row.case_number) if row.case_number else None,
                clean_text(row.case_name) if row.case_name else None,
                clean_text(row.summarize_html) if row.summarize_html else None,
                clean_text(row.case_url) if row.case_url else None
            )
            return cleaned_row
        return None
        
    except UnicodeDecodeError as e:
        error_msg = f"Unicode decode error getting case details for case_id {case_id}: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
        return None
    except Exception as e:
        error_msg = f"Database error getting case details for case_id {case_id}: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
        raise


def get_case_celebs(cursor, case_id):
    """Get case celebrities with proper error handling for encoding issues."""
    try:
        cursor.execute("""
            SELECT e.name AS celebrity_name
            FROM docketwatch.dbo.celebrities e
            INNER JOIN docketwatch.dbo.case_celebrity_matches m ON m.fk_celebrity = e.id
            WHERE m.fk_case = ?
        """, (case_id,))
        rows = cursor.fetchall()
        
        # Clean celebrity names
        cleaned_names = []
        for row in rows:
            if row.celebrity_name:
                cleaned_name = clean_text(row.celebrity_name)
                if cleaned_name:
                    cleaned_names.append(cleaned_name)
        
        return ", ".join(cleaned_names)
        
    except UnicodeDecodeError as e:
        error_msg = f"Unicode decode error getting celebrities for case_id {case_id}: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
        return ""
    except Exception as e:
        error_msg = f"Database error getting celebrities for case_id {case_id}: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
        return ""


def get_event_documents(cursor, case_id):
    """Get event documents with proper error handling for encoding issues."""
    try:
        cursor.execute("""
            SELECT e.id AS event_id, e.event_description, e.event_date, e.created_at, d.doc_uid, d.fk_case_event, d.rel_path, d.pdf_title, d.summary_ai_html, d.doc_id
            FROM docketwatch.dbo.case_events e
            LEFT JOIN docketwatch.dbo.documents d ON e.id = d.fk_case_event
            WHERE e.fk_cases = ? AND e.emailed = 0
            ORDER BY e.created_at DESC
        """, (case_id,))

        events = {}
        try:
            for row in cursor.fetchall():
                eid = row.event_id
                if eid not in events:
                    events[eid] = {
                        "event_description": clean_text(row.event_description) if row.event_description else "",
                        "event_date": row.event_date,
                        "created_at": row.created_at,
                        "documents": []
                    }
                if row.doc_id:
                    events[eid]["documents"].append({
                        "doc_id": row.doc_id,
                        "fk_case": case_id,
                        "pdf_title": clean_text(row.pdf_title) if row.pdf_title else "",
                        "summary": clean_text(row.summary_ai_html) if row.summary_ai_html else ""
                    })
        except UnicodeDecodeError as e:
            error_msg = f"Unicode decode error processing event documents for case_id {case_id}: {e}"
            logger.error(error_msg)
            error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
            # Return what we have so far, don't fail completely
        
        return events
        
    except Exception as e:
        error_msg = f"Database error getting event documents for case_id {case_id}: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
        return {}


def build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url):
    html = f"<h3>TMZ Case Update: {case_number} – {case_name}</h3>"
    if celebs:
        html += f"<p><b>Celebrities involved:</b> {celebs}</p>"
    html += f"<p><b>Internal Link:</b> <a href='{INTERNAL_URL_BASE}{case_id}#dockets'>DocketWatch</a></p>"
    if case_url:
        html += f"<p><b>External Link:</b> <a href='{case_url}'>{case_url}</a></p>"
    html += "<hr/>"

    html += f"<p>{len(events)} new case event{'s' if len(events) > 1 else ''} have been added to this case.</p><hr/>"

    for idx, (eid, info) in enumerate(events.items(), start=1):
        html += f"<h4>#{idx} – {info['event_description']}</h4>"
        html += f"<p><b>Event date:</b> {info['event_date'].strftime('%Y-%m-%d')}<br/>"
        html += f"Discovered: {info['created_at'].strftime('%Y-%m-%d %H:%M:%S')}</p>"
        num_docs = len(info['documents'])
        html += f"<p>This event includes {num_docs} document{'s' if num_docs != 1 else ''}.</p>"
        for doc in info['documents']:
            if doc["pdf_title"]:
                html += f"<p><b>{doc['pdf_title']}</b></p>"
            if doc["doc_id"]:
                pdf_link = f"{DOCS_BASE_URL}/{doc['fk_case']}/E{doc['doc_id']}.pdf"
                html += f"<p><a href='{pdf_link}'>Download PDF</a></p>"
            if doc["summary"]:
                html += doc["summary"] + "<br/>"
        html += "<hr/>"

    if case_summary:
        html += f"<h4>Case Background Summary</h4><div>{case_summary}</div><hr/>"

    return html


def send_email(subject, body, recipients):
    """Send email with proper error handling."""
    try:
        # Clean the subject and body
        subject = clean_text(subject)
        body = clean_text(body)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "html", "utf-8"))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
        logger.info(f"Email sent: {subject}")
        
    except Exception as e:
        error_msg = f"Error sending email '{subject}': {e}"
        logger.error(error_msg)
        error_notifier.log_error("Email Send Failed", error_msg, additional_context=f"Recipients: {', '.join(recipients)}")
        raise


def mark_documents_emailed(cursor, case_id):
    """Mark documents as emailed with proper error handling."""
    try:
        cursor.execute("""
            UPDATE docketwatch.dbo.documents
            SET summary_email_sent_at = GETDATE()
            WHERE fk_case = ? AND summary_email_sent_at IS NULL
        """, (case_id,))
        logger.info(f"Marked documents as emailed for case_id {case_id}")
    except Exception as e:
        error_msg = f"Error marking documents as emailed for case_id {case_id}: {e}"
        logger.error(error_msg)
        error_notifier.log_database_error(error_msg, additional_context=f"Case ID: {case_id}")
        raise


def main():
    """Main function with comprehensive error handling."""
    if len(sys.argv) < 2:
        error_msg = "Missing required case_id argument"
        logger.error(error_msg)
        error_notifier.log_critical_error(error_msg, additional_context="Script called without case_id parameter")
        return

    try:
        case_id = int(sys.argv[1])
    except ValueError as e:
        error_msg = f"Invalid case_id argument: {sys.argv[1]} - {e}"
        logger.error(error_msg)
        error_notifier.log_critical_error(error_msg)
        return

    conn, cursor = None, None
    try:
        conn, cursor = get_db_connection()
        
        case = get_case_details(cursor, case_id)
        if not case:
            logger.info(f"No case found for ID {case_id}")
            return

        _, case_number, case_name, case_summary, case_url = case
        celebs = get_case_celebs(cursor, case_id)
        events = get_event_documents(cursor, case_id)
        
        if not events:
            logger.info(f"No unemailed documents for case {case_id}")
            return

        html = build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url)
        send_email(f"TMZ Case Update: {case_number}", html, EMAIL_RECIPIENTS)
        mark_documents_emailed(cursor, case_id)
        conn.commit()
        
        logger.info(f"Successfully processed case_id {case_id}")
        
    except Exception as e:
        error_msg = f"Critical error processing case_id {case_id}: {str(e)}"
        logger.exception(error_msg)
        error_notifier.log_critical_error(
            error_msg, 
            additional_context=f"Case ID: {case_id}, Script: {script_filename}"
        )
        if conn:
            try:
                conn.rollback()
            except:
                pass
                
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as cleanup_error:
            error_msg = f"Error during cleanup: {cleanup_error}"
            logger.error(error_msg)
            error_notifier.log_database_error(error_msg)


if __name__ == "__main__":
    main()
