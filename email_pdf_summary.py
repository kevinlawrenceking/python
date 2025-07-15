import os
import pyodbc
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- Config ---
FROM_EMAIL = "it@tmz.com"
TO_EMAILS = ["Kevin.King@tmz.com"]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25
DSN = "Docketwatch"

def send_summary_email(doc_uid):
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1
            d.doc_uid,
            d.doc_id,
            d.fk_case,
            d.file_size,
            d.date_downloaded,
            d.summary_ai_html,
            d.ocr_text,
            d.pdf_url,
            c.case_name,
            c.case_url,
            c.case_number,
            e.event_no,
            e.event_description,
            e.event_date,
            e.created_at
        FROM docketwatch.dbo.documents d
        LEFT JOIN docketwatch.dbo.cases c ON d.fk_case = c.id
        LEFT JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        WHERE d.doc_uid = ?
    """, (doc_uid,))

    row = cursor.fetchone()
    if not row:
        print("Document not found.")
        return

    (doc_uid, doc_id, fk_case, file_size, date_downloaded, summary_ai_html, 
     ocr_text_raw, pdf_url, case_name, case_url, case_number, event_no, 
     event_desc, event_date, discovered_at) = row

    case_url = case_url or "(Unknown)"
    case_name = case_name or "(Unknown Case)"
    case_number = case_number or "(No Number)"
    event_no = event_no or "-"
    event_desc = event_desc or "(No Description)"
    summary_ai_html = summary_ai_html or "<p><em>No summary available.</em></p>"
    event_date_str = event_date.strftime('%B %d, %Y') if event_date else 'Unknown'
    discovered_str = discovered_at.strftime('%B %d, %Y') if discovered_at else 'Unknown'
    downloaded_str = date_downloaded.strftime('%B %d, %Y') if date_downloaded else 'Unknown'

    virtual_path = f"http://docketwatch/dwdocs/cases/{fk_case}/E{doc_id}.pdf"
    docketwatch_link = f"http://docketwatch/court/docketwatch/case_details.cfm?id={fk_case}#docket"

    subject = f"DocketWatch PDF Summary: {case_name} Docket No. {event_no} [{event_desc}]"
    body = f"""
    <html><body>
        <h2>{case_name}</h2>
        <strong>Case Number:</strong> {case_number}<br>
        <strong>Docket Entry:</strong> [{event_no}] {event_desc}<br>
        <strong>Discovered:</strong> {discovered_str}<br>
        <strong>Case Event Date:</strong> {event_date_str}<br>
        <strong>Downloaded:</strong> {downloaded_str}<br>
        <strong>Links:</strong> <a href=\"{docketwatch_link}\">DocketWatch</a> | <a href=\"{virtual_path}\">PDF</a> | <a href=\"{case_url}\">External</a>
        <hr>
        {summary_ai_html}
        <hr>
        <h3>OCR Text</h3>
        <i>Note:The OCR text may contain errors and is not guaranteed to be accurate.</i><br>
        <pre style='white-space: pre-wrap; font-family: monospace;'>{ocr_text_raw}</pre>
    </body></html>
    """

    print("--- EMAIL PREVIEW ---")
    print("TO:", TO_EMAILS)
    print("SUBJECT:", subject)
    print("BODY (HTML):\n", body)
    print("--- END PREVIEW ---")

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(TO_EMAILS)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        print("Email sent for doc_uid:", doc_uid)
    except Exception as e:
        print("Failed to send email for doc_uid:", doc_uid, "–", e)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python send_pdf_summary_email.py <doc_uid>")
    else:
        send_summary_email(sys.argv[1])
