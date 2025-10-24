"""Quick check to see what's in summary_ai_html for recent docs"""
import pyodbc

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
conn.setencoding(encoding="utf-8")
cur = conn.cursor()

# Check a doc after 10:35 on Oct 17
cur.execute("""
    SELECT TOP 1 
        doc_uid, 
        LEFT(summary_ai_html, 800) as html_preview, 
        event_summary,
        ai_processed_at
    FROM documents 
    WHERE ai_processed_at >= '2025-10-17 10:35:00' 
      AND ai_processed_at < '2025-10-17 12:00:00'
      AND summary_ai_html IS NOT NULL
    ORDER BY ai_processed_at ASC
""")

row = cur.fetchone()
if row:
    print(f"Doc UID: {row.doc_uid}")
    print(f"Processed: {row.ai_processed_at}")
    print(f"event_summary field: {repr(row.event_summary)}")
    print(f"\nHTML Preview (first 800 chars):")
    print(row.html_preview)
else:
    print("No documents found in that timeframe")

conn.close()
