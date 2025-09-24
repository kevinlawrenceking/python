import pyodbc
import logging
import os
import sys
import json
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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

# Debug mode - Set to "Y" to send emails only to Kevin for testing
DEBUG_MODE = os.getenv('DOCKETWATCH_DEBUG', 'N').upper()

EMAIL_RECIPIENTS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "marlee.chartash@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]

# Debug recipients (only Kevin)
DEBUG_RECIPIENTS = [
    "Kevin.King@tmz.com"
]


def get_db_connection():
    """Get database connection with proper error handling."""
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
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
        # NOTE: doc_id changed from int to varchar - query automatically handles this
        cursor.execute("""
            SELECT e.id AS event_id, e.event_description, e.event_date, e.created_at, 
                   d.doc_uid, d.fk_case_event, d.rel_path, d.pdf_title, d.summary_ai_html, d.doc_id,
                   d.event_summary, d.newsworthiness, d.newsworthiness_reason, 
                   d.story_headline, d.story_sub_head, d.story_body, d.whats_next
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
                        "summary": clean_text(row.summary_ai_html) if row.summary_ai_html else "",
                        "event_summary": clean_text(row.event_summary) if row.event_summary else "",
                        "newsworthiness": row.newsworthiness if hasattr(row, 'newsworthiness') and row.newsworthiness else "",
                        "newsworthiness_reason": clean_text(row.newsworthiness_reason) if row.newsworthiness_reason else "",
                        "story_headline": clean_text(row.story_headline) if row.story_headline else "",
                        "story_sub_head": clean_text(row.story_sub_head) if row.story_sub_head else "",
                        "story_body": clean_text(row.story_body) if row.story_body else "",
                        "whats_next": clean_text(row.whats_next) if row.whats_next else ""
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
    """Build enhanced HTML email using individual AI summary fields."""
    
    # Start with container and header
    html = f"""
    <div style='font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px 36px;'>
        <h2 style='color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;'>
            TMZ Case Update: {case_number} – {case_name}
        </h2>
    """
    
    # Celebrity involvement
    if celebs:
        html += f"""
        <div style='padding: 12px; border: 2px solid #ffc107; margin: 15px 0; border-radius: 6px;'>
            <strong>🌟 CELEBRITIES INVOLVED:</strong> {celebs}
        </div>
        """
    
    # Links section
    html += f"<p><b>🔗 Links:</b> <a href='{INTERNAL_URL_BASE}{case_id}#dockets'>DocketWatch</a>"
    if case_url:
        html += f" | <a href='{case_url}'>Court Website</a>"
    html += "</p>"
    


    # Process each event
    for idx, (eid, info) in enumerate(events.items(), start=1):
        html += f"""
        <div style='margin: 30px 0;'>
            <h3 style='margin: 0 0 10px 0; color: #495057; font-size: 18px;'>#{idx} – {info['event_description']}</h3>
            <p style='margin: 0 0 20px 0; color: #6c757d; font-size: 14px;'>
                <b>Event Date:</b> {info['event_date'].strftime('%B %d, %Y')} | 
                <b>Discovered:</b> {info['created_at'].strftime('%B %d, %Y at %I:%M %p')}
            </p>
        """
        
        # Process documents
        for doc in info['documents']:
            html += f"<div style='margin-left: 36px; margin-right: 36px; margin-bottom: 25px;'>"
            
            if doc["pdf_title"]:
                # Create friendly attachment name
                friendly_name = doc["pdf_title"]
                if len(friendly_name) > 50:
                    friendly_name = friendly_name[:47] + "..."
                
                html += f"""
                <div style='padding: 8px 0; margin-bottom: 15px;'>
                    <strong>📋 Document:</strong> {friendly_name} 
                    <span style='color: #28a745; font-size: 12px; font-weight: bold;'>✓ ATTACHED</span>
                </div>
                """
            
            # Use new AI summary fields for better formatting
            if doc["event_summary"]:
                html += f"""
                <div style='margin: 15px 0;'>
                    <h4 style='color: #495057; margin-bottom: 10px; font-size: 16px;'>📄 Summary</h4>
                    <div style='line-height: 1.6;'>
                        {doc["event_summary"]}
                    </div>
                </div>
                """
            
            # Newsworthy highlight
            if doc["newsworthiness"] and doc["newsworthiness"].upper() == "YES":
                html += f"""
                <div style='margin: 15px 0;'>
                    <strong>📰 NEWSWORTHY:</strong> {doc["newsworthiness_reason"] or "This document contains newsworthy information."}
                </div>
                """
            
            # TMZ Story section - the main feature
            if doc["story_headline"] and doc["story_body"]:
                html += f"""
                <div style='border: 2px solid #e74c3c; padding: 20px; margin: 20px 0; border-radius: 8px;'>
                    <div style='text-align: center; margin-bottom: 15px;'>
                        <span style='color: #e74c3c; padding: 6px 12px; border-radius: 4px; font-weight: bold; font-size: 14px; border: 1px solid #e74c3c;'>
                            📺 TMZ EXCLUSIVE
                        </span>
                    </div>
                    <h2 style='color: #e74c3c; margin-top: 0; font-size: 24px; line-height: 1.2; text-align: center;'>
                        {doc["story_headline"]}
                    </h2>
                """
                
                if doc["story_sub_head"]:
                    html += f"""
                    <h3 style='color: #d35400; font-size: 16px; font-style: italic; text-align: center; margin-bottom: 20px; font-weight: 500;'>
                        {doc["story_sub_head"]}
                    </h3>
                    """
                
                # Format story body with proper paragraphs
                story_paragraphs = doc["story_body"].split('\n\n') if doc["story_body"] else []
                for paragraph in story_paragraphs:
                    if paragraph.strip():
                        html += f"""
                        <p style='line-height: 1.7; margin-bottom: 16px; font-size: 15px; text-align: justify;'>
                            {paragraph.strip()}
                        </p>
                        """
                
                html += f"</div>"
            
            # What's Next section
            if doc["whats_next"]:
                html += f"""
                <div style='margin: 15px 0;'>
                    <strong>🔮 WHAT'S NEXT:</strong> {doc["whats_next"]}
                </div>
                """
            
            # Fallback to old summary field if new fields are empty
            elif doc["summary"] and not doc["event_summary"]:
                html += f"<div style='margin: 15px 0;'>{doc['summary']}</div>"
            
            html += f"</div>"  # Close document div
        
        html += f"</div>"  # Close event div

    # Case background summary
    if case_summary:
        html += f"""
        <div style='margin: 30px 0 20px 0;'>
            <h4 style='color: #1976d2; margin-top: 0; font-size: 16px;'>📋 Case Background Summary</h4>
            <div style='line-height: 1.6;'>{case_summary}</div>
        </div>
        """

    html += "</div>"  # Close main container
    return html


def send_email(subject, body, recipients, events=None):
    """Send email with proper error handling and PDF attachments."""
    try:
        # Clean the subject and body
        subject = clean_text(subject)
        body = clean_text(body)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "html", "utf-8"))
        
        # Add PDF attachments if events provided
        if events:
            for eid, info in events.items():
                for doc in info['documents']:
                    if doc["doc_id"]:
                        try:
                            pdf_url = f"{DOCS_BASE_URL}/{doc['fk_case']}/E{doc['doc_id']}.pdf"
                            
                            # Create friendly filename
                            if doc.get("pdf_title"):
                                # Clean the title for filename
                                friendly_name = doc["pdf_title"][:50]  # Limit length
                                friendly_name = "".join(c for c in friendly_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                friendly_name = friendly_name.replace(' ', '_')
                                pdf_filename = f"{friendly_name}_{doc['doc_id']}.pdf"
                            else:
                                pdf_filename = f"Document_{doc['doc_id']}.pdf"
                            
                            # Try to fetch the PDF
                            response = requests.get(pdf_url, timeout=30)
                            if response.status_code == 200:
                                # Create attachment
                                attachment = MIMEBase('application', 'pdf')
                                attachment.set_payload(response.content)
                                encoders.encode_base64(attachment)
                                attachment.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename="{pdf_filename}"'
                                )
                                msg.attach(attachment)
                                logger.info(f"Added PDF attachment: {pdf_filename}")
                            else:
                                logger.warning(f"Could not fetch PDF: {pdf_url} (status: {response.status_code})")
                        except Exception as pdf_error:
                            logger.warning(f"Failed to attach PDF {pdf_url}: {pdf_error}")
        
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
    # Log debug mode status
    if DEBUG_MODE == 'Y':
        logger.info("🔧 DEBUG MODE ENABLED - Emails will only be sent to debug recipients")
        logger.info(f"Debug recipients: {DEBUG_RECIPIENTS}")
    else:
        logger.info("📧 Production mode - Emails will be sent to all recipients")
        logger.info(f"Production recipients: {EMAIL_RECIPIENTS}")
    
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

        # Determine recipients based on debug mode
        recipients = DEBUG_RECIPIENTS if DEBUG_MODE == 'Y' else EMAIL_RECIPIENTS
        if DEBUG_MODE == 'Y':
            logger.info(f"DEBUG MODE: Sending email only to debug recipients: {recipients}")
        
        # Create email subject with debug prefix if in debug mode
        subject = f"TMZ Case Update: {case_number}"
        if DEBUG_MODE == 'Y':
            subject = f"[DEBUG] {subject}"
        
        html = build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url)
        send_email(subject, html, recipients, events)
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