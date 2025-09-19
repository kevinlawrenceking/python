import pyodbc
import subprocess
import time

# --- Database connection ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Query to find case_events with pending documents (need PDF download) ---
cursor.execute("""
    SELECT TOP 10 
        ce.id,
        ce.event_no,
        ce.event_description,
        c.case_number,
        COUNT(d.doc_uid) as pending_docs
    FROM docketwatch.dbo.case_events ce
    INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
    INNER JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_event
    WHERE d.rel_path = 'pending'
    GROUP BY ce.id, ce.event_no, ce.event_description, c.case_number
    ORDER BY MAX(d.date_downloaded) DESC
""")
case_events = cursor.fetchall()
print(f"Found {len(case_events)} case_events with pending documents (need PDF download).")

# --- Run PDF download script for each case_event ---
for row in case_events:
    case_id = row.id
    event_no = row.event_no
    case_number = row.case_number
    pending_docs = row.pending_docs
    print(f"\n[INFO] Running process_pacer_event_pdf_final.py for case_event ID: {case_id} (Event {event_no}, Case {case_number}, {pending_docs} pending docs)")
    try:
        subprocess.run([
            "python",
            "u:\\docketwatch\\python\\process_pacer_event_pdf_final.py",
            str(case_id)
        ], check=True)
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PDF download failed on case_event {case_id}: {e}")

cursor.close()
conn.close()