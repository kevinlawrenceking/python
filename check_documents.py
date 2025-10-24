import pyodbc

DSN = "Docketwatch"

def get_cursor():
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn, conn.cursor()

conn, cur = get_cursor()

# Check by case event ID
event_id = 'E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6'
print(f"\n=== Documents for Case Event: {event_id} ===")
cur.execute("""
    SELECT 
        doc_uid,
        pdf_title,
        date_downloaded,
        fk_case,
        fk_case_event,
        event_summary,
        newsworthiness,
        CASE WHEN summary_ai_html IS NOT NULL THEN 1 ELSE 0 END as has_summary,
        CASE WHEN ocr_text IS NOT NULL THEN 1 ELSE 0 END as has_ocr
    FROM docketwatch.dbo.documents
    WHERE fk_case_event = CAST(? AS uniqueidentifier)
    ORDER BY date_downloaded DESC
""", (event_id,))

rows = cur.fetchall()
if rows:
    print(f"Found {len(rows)} documents:")
    for row in rows:
        print(f"\n  doc_uid: {row.doc_uid}")
        print(f"  title: {row.pdf_title}")
        print(f"  downloaded: {row.date_downloaded}")
        print(f"  case_id: {row.fk_case}")
        print(f"  event_summary: {row.event_summary[:100] if row.event_summary else 'NULL'}")
        print(f"  newsworthiness: {row.newsworthiness}")
        print(f"  has_summary: {row.has_summary}")
        print(f"  has_ocr: {row.has_ocr}")
else:
    print("No documents found for this case event")

# Check by case ID
case_id = 255815
print(f"\n\n=== Documents for Case ID: {case_id} ===")
cur.execute("""
    SELECT 
        doc_uid,
        pdf_title,
        date_downloaded,
        fk_case,
        fk_case_event,
        event_summary,
        newsworthiness,
        CASE WHEN summary_ai_html IS NOT NULL THEN 1 ELSE 0 END as has_summary,
        CASE WHEN ocr_text IS NOT NULL THEN 1 ELSE 0 END as has_ocr
    FROM docketwatch.dbo.documents
    WHERE fk_case = ?
    ORDER BY date_downloaded DESC
""", (case_id,))

rows = cur.fetchall()
if rows:
    print(f"Found {len(rows)} documents:")
    for row in rows:
        print(f"\n  doc_uid: {row.doc_uid}")
        print(f"  title: {row.pdf_title}")
        print(f"  downloaded: {row.date_downloaded}")
        print(f"  event_id: {row.fk_case_event}")
        print(f"  event_summary: {row.event_summary[:100] if row.event_summary else 'NULL'}")
        print(f"  newsworthiness: {row.newsworthiness}")
        print(f"  has_summary: {row.has_summary}")
        print(f"  has_ocr: {row.has_ocr}")
else:
    print("No documents found for this case")

# Check the case event details
print(f"\n\n=== Case Event Details: {event_id} ===")
cur.execute("""
    SELECT 
        id,
        fk_cases,
        event_description,
        event_date,
        summarize
    FROM docketwatch.dbo.case_events
    WHERE id = CAST(? AS uniqueidentifier)
""", (event_id,))

event = cur.fetchone()
if event:
    print(f"Event found:")
    print(f"  event_id: {event.id}")
    print(f"  case_id: {event.fk_cases}")
    print(f"  description: {event.event_description}")
    print(f"  date: {event.event_date}")
    print(f"  summarize: {event.summarize[:200] if event.summarize else 'NULL'}")
else:
    print("Case event not found")

cur.close()
conn.close()
