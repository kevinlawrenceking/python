import pyodbc
import subprocess
import time

# --- Connect to database ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Find case_event IDs that don't have matching documents yet ---
cursor.execute("""
    SELECT top 1 id AS case_id 
    FROM docketwatch.dbo.case_events 
    WHERE event_url IS NOT NULL 
      AND id NOT IN (
        SELECT DISTINCT fk_case_event FROM docketwatch.dbo.documents
        WHERE fk_case_event IS NOT NULL
      )
      AND fk_cases IN (
        SELECT id FROM docketwatch.dbo.cases
      )
    ORDER BY created_at DESC
""")

case_ids = [row.case_id for row in cursor.fetchall()]
print(f"Found {len(case_ids)} case_events to process.")

# --- Run metadata extraction per case_event ---
for case_id in case_ids:
    print(f"Running for case_event ID: {case_id}")
    try:
        subprocess.run([
            "python",
            "u:\\docketwatch\\python\\extract_pacer_pdf_metadata.py",
            str(case_id)
        ], check=True)
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"Error running script for case_event {case_id}: {e}")

cursor.close()
conn.close()
