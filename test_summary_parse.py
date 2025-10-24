"""
Quick test to check if summary parsing is working correctly
"""
import pyodbc
from summary_parser import parse_ai_summary

# Get a recent successful summary
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
conn.setencoding(encoding="utf-8")
cur = conn.cursor()

cur.execute("""
    SELECT TOP 1 doc_uid, summary_ai_html, event_summary
    FROM docketwatch.dbo.documents 
    WHERE summary_ai_html IS NOT NULL 
      AND ai_processed_at >= DATEADD(day, -2, GETDATE())
    ORDER BY ai_processed_at DESC
""")

row = cur.fetchone()
if row:
    doc_uid, html, current_event_summary = row
    print(f"Testing doc_uid: {doc_uid}")
    print(f"Current event_summary in DB: {repr(current_event_summary)}")
    print(f"\nHTML length: {len(html) if html else 0}")
    print(f"\nFirst 500 chars of HTML:\n{html[:500] if html else 'None'}")
    print("\n" + "="*80)
    
    # Parse it
    parsed = parse_ai_summary(html)
    print(f"\nParsed event_summary: {repr(parsed.get('event_summary'))}")
    print(f"Parsed newsworthiness: {repr(parsed.get('newsworthiness'))}")
    print(f"Parsed headline: {repr(parsed.get('story_headline'))}")
    print(f"Parsed key_details count: {len(parsed.get('key_details', []))}")
else:
    print("No recent summaries found")

conn.close()
