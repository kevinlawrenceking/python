import pyodbc
import subprocess
import time

# --- Database connection ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Query to find unprocessed case_event IDs ---
cursor.execute("""
    SELECT TOP 10 id
    FROM docketwatch.dbo.case_events
    WHERE event_url IS NOT NULL
      AND id NOT IN (
          SELECT DISTINCT fk_case_event
          FROM docketwatch.dbo.documents
          WHERE fk_case_event IS NOT NULL
      )
    ORDER BY created_at DESC
""")
case_ids = [row.id for row in cursor.fetchall()]
print(f"Found {len(case_ids)} unprocessed case_events.")

# --- Run merged script for each case_event ---
for case_id in case_ids:
    print(f"\n[INFO] Running process_pacer_event_pdf.py for case_event ID: {case_id}")
    try:
        subprocess.run([
            "python",
            "u:\\docketwatch\\python\\process_pacer_event_pdf.py",
            str(case_id)
        ], check=True)
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Script failed on case_event {case_id}: {e}")

cursor.close()
conn.close()
