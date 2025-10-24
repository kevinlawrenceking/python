"""Check what's actually in one of those docs"""
import pyodbc
from summary_parser import parse_ai_summary

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
conn.setencoding(encoding="utf-8")
cur = conn.cursor()

# Check the first doc
cur.execute("""
    SELECT doc_uid, summary_ai_html, event_summary, ai_processed_at
    FROM documents 
    WHERE doc_uid = 'DE7DB8EA-5557-410B-8D5C-2930D7C1D6DD'
""")

row = cur.fetchone()
if row:
    print(f"Doc UID: {row.doc_uid}")
    print(f"Processed: {row.ai_processed_at}")
    print(f"Current event_summary: {repr(row.event_summary)}")
    print(f"\nHTML (first 500 chars):")
    print(row.summary_ai_html[:500] if row.summary_ai_html else "None")
    print("\nTrying to parse...")
    if row.summary_ai_html:
        parsed = parse_ai_summary(row.summary_ai_html)
        print(f"Parsed event_summary: {repr(parsed['event_summary'])}")

conn.close()
