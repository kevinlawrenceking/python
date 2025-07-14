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

# Setup logging
script_filename = os.path.splitext(os.path.basename(__file__))[0]
log_dir = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, f"{script_filename}.log")
logging.basicConfig(filename=log_path, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Config
FROM_EMAIL = "it@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25
INTERNAL_URL_BASE = "http://tmztools.tmz.local/court/docketwatch/case_details.cfm?id="
DOCS_BASE_URL = "http://tmztools.tmz.local/dwdocs/cases"
EMAIL_RECIPIENTS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "Marlee.Goodman@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]


def get_db_connection():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    return conn, conn.cursor()


def get_case_details(cursor, case_id):
    cursor.execute("""
        SELECT c.id, c.case_number, c.case_name, c.summarize_html, c.case_url
        FROM docketwatch.dbo.cases c
        WHERE c.id = ?
    """, (case_id,))
    return cursor.fetchone()


def get_case_celebs(cursor, case_id):
    cursor.execute("""
        SELECT e.name AS celebrity_name
        FROM docketwatch.dbo.celebrities e
        INNER JOIN docketwatch.dbo.case_celebrity_matches m ON m.fk_celebrity = e.id
        WHERE m.fk_case = ?
    """, (case_id,))
    rows = cursor.fetchall()
    return ", ".join(row.celebrity_name for row in rows if row.celebrity_name)


def get_event_documents(cursor, case_id):
    cursor.execute("""
        SELECT e.id AS event_id, e.event_description, e.event_date, e.created_at, d.doc_uid, d.fk_case_event, d.rel_path, d.pdf_title, d.summary_ai_html, d.doc_id
        FROM docketwatch.dbo.case_events e
        LEFT JOIN docketwatch.dbo.documents d ON e.id = d.fk_case_event
        WHERE e.fk_cases = ? AND e.emailed = 0
        ORDER BY e.created_at DESC
    """, (case_id,))

    events = {}
    for row in cursor.fetchall():
        eid = row.event_id
        if eid not in events:
            events[eid] = {
                "event_description": row.event_description,
                "event_date": row.event_date,
                "created_at": row.created_at,
                "documents": []
            }
        if row.doc_id:
            events[eid]["documents"].append({
                "doc_id": row.doc_id,
                "fk_case": case_id,
                "pdf_title": row.pdf_title,
                "summary": row.summary_ai_html
            })
    return events


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
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "html"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
        logger.info(f"Email sent: {subject}")
    except Exception as e:
        logger.error(f"Error sending email: {e}")


def mark_documents_emailed(cursor, case_id):
    cursor.execute("""
        UPDATE docketwatch.dbo.documents
        SET summary_email_sent_at = GETDATE()
        WHERE fk_case = ? AND summary_email_sent_at IS NULL
    """, (case_id,))


def main():
    if len(sys.argv) < 2:
        logger.error("Missing required case_id argument")
        return

    case_id = int(sys.argv[1])
    conn, cursor = get_db_connection()
    try:
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
    except Exception as e:
        logger.exception("Unhandled error")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
