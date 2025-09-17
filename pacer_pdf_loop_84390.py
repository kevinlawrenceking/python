import pyodbc
import subprocess
import time

# --- Database connection ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Query to find case_events with NO documents (need metadata extraction) ---
cursor.execute("""
    SELECT TOP 10 
        ce.id,
        ce.event_no,
        ce.event_description,
        c.case_number
    FROM docketwatch.dbo.case_events ce
    INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
    INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    LEFT JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_event
    WHERE t.tool_name = 'Pacer'
        AND ce.event_url IS NOT NULL 
        AND ce.event_url != ''
        AND d.doc_uid IS NULL  -- No documents exist yet
    ORDER BY ce.event_date DESC, ce.id DESC
""")
case_events = cursor.fetchall()
print(f"Found {len(case_events)} case_events with no documents (need metadata extraction).")

# --- Run metadata extraction script for each case_event ---
for row in case_events:
    case_id = row.id
    event_no = row.event_no
    case_number = row.case_number
    print(f"\n[INFO] Running extract_pacer_pdf_metadata.py for case_event ID: {case_id} (Event {event_no}, Case {case_number})")
    try:
        subprocess.run([
            "C:\\Program Files\\Python312\\python.exe",
            "u:\\docketwatch\\python\\extract_pacer_pdf_metadata.py",
            str(case_id)
        ], check=True)
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Metadata extraction failed on case_event {case_id}: {e}")

cursor.close()
conn.close()
