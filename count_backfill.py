"""Quick count of documents needing backfill"""
import pyodbc

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cur = conn.cursor()

# Count all that need backfill
cur.execute("""
    SELECT COUNT(*) as total
    FROM docketwatch.dbo.documents
    WHERE ocr_text IS NOT NULL
      AND event_summary IS NULL
      AND pdf_type = 'Docket'
      AND summary_ai_html IS NOT NULL
""")
total = cur.fetchone()[0]
print(f"Total documents needing backfill: {total}")

# Count since Oct 17
cur.execute("""
    SELECT COUNT(*) as total
    FROM docketwatch.dbo.documents
    WHERE ocr_text IS NOT NULL
      AND event_summary IS NULL
      AND pdf_type = 'Docket'
      AND summary_ai_html IS NOT NULL
      AND ai_processed_at >= '2025-10-17 10:35:00'
""")
recent = cur.fetchone()[0]
print(f"Documents since Oct 17 10:35am: {recent}")

conn.close()
