import pyodbc
import logging
import os
import sys
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import smtplib
from bs4 import BeautifulSoup
from error_notification_system import create_error_notifier

# Setup logging
script_filename = os.path.        html += f"<div style='padding: 10px 0; border-left: 4px solid #dc3545; padding-left: 15px; margin: 15px 0;'>"
        html += f"<p style='margin: 0; color: #721c24; font-size: 14px;'><strong>📝 NOTE:</strong> Document reviewed but not considered newsworthy at this time.</p>"
        html += "</div>"
    
    # Fallback to old summary if no event_summary but has old summary - simplified
    elif doc.get("summary") and not event_summary:
        html += f"<div style='padding: 12px 0; border-left: 4px solid #6c757d; padding-left: 15px; margin: 15px 0;'>"
        html += f"<h5 style='color: #6c757d; margin-top: 0; font-size: 14px;'>Legacy Summary</h5>"
        html += f"<div style='font-size: 14px; line-height: 1.5;'>{doc['summary']}</div>"
        html += "</div>"s.path.basename(__file__))[0]

# === Initialize error notification system ===
error_notifier = create_error_notifier(script_filename)

log_dir = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, f"{script_filename}.log")
logging.basicConfig(filename=log_path, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Config
dbug = "Y"  # Set to "Y" for debugging - emails will only go to Kevin
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
DEBUG_EMAIL_RECIPIENTS = [
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
                   d.story_headline, d.story_sub_head, d.story_body, d.whats_next, d.pdf_type
            FROM docketwatch.dbo.case_events e
            LEFT JOIN docketwatch.dbo.documents d ON e.id = d.fk_case_event
            WHERE e.fk_cases = ? AND e.emailed = 0
            ORDER BY e.created_at DESC, d.pdf_type ASC
        """, (case_id,))

        events = {}
        rows = cursor.fetchall()
        
        try:
            for row in rows:
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
                        "pdf_type": row.pdf_type if row.pdf_type else "Document",
                        "summary": clean_text(row.summary_ai_html) if row.summary_ai_html else "",
                        "rel_path": row.rel_path if row.rel_path else "",
                        # Add the new AI summary fields
                        "event_summary": clean_text(row.event_summary) if row.event_summary else "",
                        "newsworthiness": row.newsworthiness if row.newsworthiness else None,
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


def build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url, attachment_count=0):
    """Build enhanced HTML email with comprehensive case information."""
    
    # Header section with improved padding and responsive design
    html = f"<div style='font-family: Arial, sans-serif; max-width: 900px; padding: 0 20px; margin: 0 auto;'>"
    html += f"<h2 style='color: #e74c3c; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; margin-top: 20px;'>TMZ Case Update: {case_number}</h2>"
    html += f"<h3 style='color: #2c3e50; margin-top: 0;'>{case_name}</h3>"
    
    if celebs:
        html += f"<p style='padding: 10px 0; border-left: 4px solid #ffc107; padding-left: 15px; margin: 15px 0;'>"
        html += f"<strong>🌟 CELEBRITIES INVOLVED:</strong> {celebs}</p>"
    
    # Links section - simplified
    html += f"<div style='padding: 15px 0; border-bottom: 1px solid #dee2e6; margin: 15px 0;'>"
    html += f"<p><strong>🔗 Links:</strong> "
    html += f"<a href='{INTERNAL_URL_BASE}{case_id}#dockets' style='color: #007bff; text-decoration: none; margin-right: 15px;'>DocketWatch</a>"
    if case_url:
        html += f"<a href='{case_url}' style='color: #007bff; text-decoration: none;'>Court Website</a>"
    html += "</p>"
    
    # Attachment information - simplified
    if attachment_count > 0:
        html += f"<p style='margin: 10px 0 0 0; color: #28a745; font-weight: bold;'>📎 {attachment_count} PDF document{'s' if attachment_count > 1 else ''} attached to this email</p>"
    html += "</div>"
    
    # Case summary section (if available) - simplified
    if case_summary:
        html += f"<div style='padding: 15px 0; border-left: 4px solid #2196f3; padding-left: 15px; margin: 20px 0;'>"
        html += f"<h4 style='color: #1976d2; margin-top: 0;'>📋 Case Background Summary</h4>"
        html += f"<div style='line-height: 1.6;'>{case_summary}</div>"
        html += "</div>"

    # Events header - simplified
    html += f"<div style='padding: 15px 0; border-top: 2px solid #27ae60; margin: 20px 0;'>"
    html += f"<h3 style='color: #27ae60; margin: 0;'>📄 {len(events)} New Case Event{'s' if len(events) > 1 else ''}</h3>"
    html += "</div>"

    # Process each event
    for idx, (eid, info) in enumerate(events.items(), start=1):
        html += f"<div style='border: 2px solid #bdc3c7; border-radius: 10px; margin: 25px 0; padding: 0; overflow: hidden;'>"
        
        # Event header - simplified
        html += f"<div style='background-color: #34495e; color: white; padding: 15px;'>"
        html += f"<h3 style='margin: 0; font-size: 18px;'>#{idx} – {info['event_description']}</h3>"
        html += f"<p style='margin: 8px 0 0 0; opacity: 0.9;'>"
        html += f"<strong>Event Date:</strong> {info['event_date'].strftime('%B %d, %Y') if info['event_date'] else 'Not specified'} | "
        html += f"<strong>Discovered:</strong> {info['created_at'].strftime('%B %d, %Y at %I:%M %p') if info['created_at'] else 'Unknown'}"
        html += f"</p></div>"
        
        # Document count and types - simplified
        num_docs = len(info['documents'])
        docket_docs = [d for d in info['documents'] if d.get('pdf_type') == 'Docket']
        attachment_docs = [d for d in info['documents'] if d.get('pdf_type') == 'Attachment']
        
        html += f"<div style='padding: 15px; border-bottom: 1px solid #dee2e6;'>"
        html += f"<p style='margin: 0; color: #6c757d;'>"
        html += f"<strong>📑 Documents:</strong> {num_docs} total"
        if docket_docs:
            html += f" ({len(docket_docs)} main document{'s' if len(docket_docs) > 1 else ''}"
            if attachment_docs:
                html += f", {len(attachment_docs)} attachment{'s' if len(attachment_docs) > 1 else ''})"
            else:
                html += ")"
        elif attachment_docs:
            html += f" ({len(attachment_docs)} attachment{'s' if len(attachment_docs) > 1 else ''})"
        html += "</p></div>"
        
        # Process main documents first (Docket type)
        main_doc_processed = False
        for doc in docket_docs:
            html += process_document_html(doc, "Main Document", is_main=True)
            main_doc_processed = True
        
        # Process attachments
        for i, doc in enumerate(attachment_docs, 1):
            attachment_label = f"Attachment {i}" if len(attachment_docs) > 1 else "Attachment"
            html += process_document_html(doc, attachment_label, is_main=False)
        
        # If no main document, process other documents
        if not main_doc_processed:
            other_docs = [d for d in info['documents'] if d.get('pdf_type') not in ['Docket', 'Attachment']]
            for i, doc in enumerate(other_docs, 1):
                doc_label = f"Document {i}" if len(other_docs) > 1 else "Document"
                html += process_document_html(doc, doc_label, is_main=True)
        
        html += "</div>"  # Close event container

    html += "</div>"  # Close main container
    return html


def process_document_html(doc, doc_label, is_main=False):
    """Process individual document HTML with enhanced formatting."""
    
    html = f"<div style='padding: 20px; border-top: 1px solid #dee2e6;'>"
    
    # Document header with type (removed download link for attached docs)
    html += f"<div style='margin-bottom: 15px;'>"
    html += f"<h4 style='color: #495057; margin: 0;'>"
    
    # Add icon based on document type
    icon = "📋" if is_main else "📎"
    html += f"{icon} <strong>{doc_label}:</strong> {doc['pdf_title']}"
    
    # Attachment status
    rel_path = doc.get("rel_path", "")
    is_attached = rel_path and rel_path != "pending"
    if is_attached:
        html += " <span style='color: #28a745; font-size: 12px; font-weight: bold;'>✓ ATTACHED</span>"
    else:
        html += " <span style='color: #ffc107; font-size: 12px; font-weight: bold;'>⏳ PENDING</span>"
        # Only show download link for pending documents
        if doc["doc_id"]:
            pdf_link = f"{DOCS_BASE_URL}/{doc['fk_case']}/E{doc['doc_id']}.pdf"
            html += f"<br><a href='{pdf_link}' style='background-color: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px; margin-top: 8px; display: inline-block;'>DOWNLOAD PDF</a>"
    
    html += "</h4></div>"
    
    # Content sections
    event_summary = doc.get("event_summary", "")
    newsworthiness = doc.get("newsworthiness", "")
    has_story = doc.get("story_headline") and doc.get("story_body")
    
    # Main summary (always show if available) - simplified
    if event_summary:
        # Handle truncated summaries better
        summary_text = event_summary.strip()
        if len(summary_text) > 500 and not summary_text.endswith(('.', '!', '?')):
            # If it looks truncated, add ellipsis and a note
            summary_text += "... [Summary continues in attached document]"
        
        html += f"<div style='padding: 15px 0; border-left: 4px solid #6c757d; padding-left: 15px; margin: 15px 0;'>"
        html += f"<h5 style='color: #495057; margin-top: 0;'>📖 Summary</h5>"
        html += f"<p style='line-height: 1.6; margin-bottom: 0;'>{summary_text}</p>"
        html += "</div>"
    
    # Newsworthiness indicator - simplified
    if newsworthiness == "Yes":
        reason = doc.get("newsworthiness_reason", "This document has significant news value")
        # Ensure the reason text isn't truncated
        if len(reason) > 200 and not reason.endswith('.'):
            reason += "..."
        html += f"<div style='padding: 12px 0; border-left: 4px solid #28a745; padding-left: 15px; margin: 15px 0;'>"
        html += f"<p style='margin: 0; color: #155724;'><strong>📰 NEWSWORTHY:</strong> {reason}</p>"
        html += "</div>"
        
        # Full story section (only if newsworthy AND has story content)
        if has_story:
            html += f"<div style='border: 2px solid #e74c3c; padding: 20px; margin: 20px 0; background-color: #fef9e7; border-radius: 8px;'>"
            html += f"<h3 style='color: #e74c3c; margin-top: 0; font-size: 22px; line-height: 1.3;'>{doc['story_headline']}</h3>"
            
            if doc.get("story_sub_head"):
                html += f"<h4 style='color: #d35400; font-size: 16px; font-style: italic; margin-bottom: 20px; font-weight: 500;'>{doc['story_sub_head']}</h4>"
            
            # Format the story body with TMZ-style paragraphs
            story_body = doc.get("story_body", "")
            if story_body:
                paragraphs = [p.strip() for p in story_body.split('\n\n') if p.strip()]
                for paragraph in paragraphs:
                    html += f"<p style='line-height: 1.7; margin-bottom: 16px; font-size: 15px;'>{paragraph}</p>"
            
            # What's Next section - improved handling with simplified styling
            whats_next_text = doc.get("whats_next", "").strip()
            if whats_next_text and whats_next_text.lower() not in ["no specific next steps mentioned in this document.", "none mentioned.", "not specified."]:
                html += f"<div style='padding: 12px 0; border-left: 4px solid #2196f3; padding-left: 15px; margin: 15px 0;'>"
                html += f"<p style='margin: 0; color: #0d47a1;'><strong>🔮 WHAT'S NEXT:</strong> {whats_next_text}</p>"
                html += "</div>"
            else:
                # Add a generic but useful next steps section
                html += f"<div style='padding: 12px 0; border-left: 4px solid #6c757d; padding-left: 15px; margin: 15px 0;'>"
                html += f"<p style='margin: 0; color: #495057;'><strong>👀 FOLLOW-UP:</strong> Monitor for responses from opposing counsel and any scheduling orders from the court.</p>"
                html += "</div>"
            
            html += "</div>"
    
    elif newsworthiness == "No":
        html += f"<div style='background-color: #f8d7da; padding: 10px; border-left: 4px solid #dc3545; margin: 15px 0; border-radius: 4px;'>"
        html += f"<p style='margin: 0; color: #721c24; font-size: 14px;'><strong>� NOTE:</strong> Document reviewed but not considered newsworthy at this time.</p>"
        html += "</div>"
    
    # Fallback to old summary if no event_summary but has old summary
    elif doc.get("summary") and not event_summary:
        html += f"<div style='background-color: #f4f4f4; padding: 12px; border-radius: 4px; margin: 15px 0;'>"
        html += f"<h5 style='color: #6c757d; margin-top: 0; font-size: 14px;'>Legacy Summary</h5>"
        html += f"<div style='font-size: 14px; line-height: 1.5;'>{doc['summary']}</div>"
        html += "</div>"
    
    html += "</div>"
    return html


def send_email(subject, body, recipients, attachments=None):
    """Send email with proper error handling and optional PDF attachments."""
    try:
        # Clean the subject and body
        subject = clean_text(subject)
        body = clean_text(body)
        
        msg = MIMEMultipart("mixed")  # Changed to "mixed" to support attachments
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(recipients)
        
        # Add HTML body
        html_part = MIMEMultipart("alternative")
        html_part.attach(MIMEText(body, "html", "utf-8"))
        msg.attach(html_part)
        
        # Add PDF attachments if provided
        attached_count = 0
        if attachments:
            for file_path, filename in attachments:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    try:
                        with open(file_path, 'rb') as f:
                            pdf_attachment = MIMEApplication(f.read(), _subtype='pdf')
                            pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                            msg.attach(pdf_attachment)
                            attached_count += 1
                            logger.info(f"Attached PDF: {filename}")
                    except Exception as e:
                        logger.warning(f"Could not attach PDF {filename}: {e}")
                else:
                    logger.warning(f"PDF file not found or empty: {file_path}")
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
        
        attach_info = f" (with {attached_count} PDF attachments)" if attached_count > 0 else ""
        logger.info(f"Email sent: {subject}{attach_info}")
        
    except Exception as e:
        error_msg = f"Error sending email '{subject}': {e}"
        logger.error(error_msg)
        error_notifier.log_error("Email Send Failed", error_msg, additional_context=f"Recipients: {', '.join(recipients)}")
        raise


def collect_pdf_attachments(events, base_docs_dir):
    """Collect PDF attachments from event documents."""
    attachments = []
    
    for event_id, event_data in events.items():
        for doc in event_data["documents"]:
            rel_path = doc.get("rel_path", "")
            doc_id = doc.get("doc_id", "")
            pdf_title = doc.get("pdf_title", "")
            fk_case = doc.get("fk_case", "")
            
            # Skip if no doc_id (document not available)
            if not doc_id or not fk_case:
                logger.info(f"Skipping attachment for doc: missing doc_id or fk_case")
                continue
            
            # Skip if no relative path (document not downloaded yet)
            if not rel_path or rel_path == "pending":
                logger.info(f"Skipping attachment for doc_id {doc_id}: not downloaded yet (rel_path: {rel_path})")
                continue
            
            # Construct full file path using the standard formula:
            # \\10.146.176.84\general\docketwatch\docs\cases\{fk_case}\E{doc_id}.pdf
            full_path = f"{base_docs_dir}\\cases\\{fk_case}\\E{doc_id}.pdf"
            
            # Create a clean filename for the attachment
            if pdf_title:
                # Use PDF title but ensure it's a valid filename
                clean_title = "".join(c for c in pdf_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{clean_title}.pdf" if not clean_title.endswith('.pdf') else clean_title
            else:
                filename = f"Document_{doc_id}.pdf"
            
            # Ensure filename isn't too long
            if len(filename) > 100:
                filename = f"Document_{doc_id}.pdf"
            
            attachments.append((full_path, filename))
            logger.info(f"Prepared attachment: {filename} from {full_path}")
    
    return attachments


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

        # Collect PDF attachments from documents
        attachments = collect_pdf_attachments(events, r"\\10.146.176.84\general\docketwatch\docs")
        
        html = build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url, len(attachments))
        
        # Determine recipients based on debug mode
        recipients = DEBUG_EMAIL_RECIPIENTS if dbug.upper() == "Y" else EMAIL_RECIPIENTS
        if dbug.upper() == "Y":
            logger.info(f"DEBUG MODE: Email will only be sent to Kevin for case {case_number}")
        
        # Log attachment info
        if attachments:
            logger.info(f"Sending email with {len(attachments)} PDF attachments for case {case_number}")
        else:
            logger.info(f"Sending email with no attachments for case {case_number}")
        
        send_email(f"TMZ Case Update: {case_number}", html, recipients, attachments)
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
