
import os
import pyodbc
import logging
from case_processing import process_case
from celebrity_matches import check_celebrity_matches

# === CONFIGURATION ===
DSN = "Docketwatch"
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === DATABASE CONNECTION ===
conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
cursor = conn.cursor()

# === Get Latest fk_task_run for Logging ===
cursor.execute("""
    SELECT TOP 1 r.id as fk_task_run
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
    WHERE s.filename = ?
    ORDER BY r.id DESC
""", (script_filename,))
task_run = cursor.fetchone()
fk_task_run = task_run[0] if task_run else None

# === Log Helper ===
def log_message(log_type, message):
    logging.info(message)
    if fk_task_run:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?)
            """, (fk_task_run, log_type, message))
            conn.commit()
        except Exception as e:
            logging.error(f"Failed to write to task_runs_log: {e}")

log_message("INFO", "=== Starting docketwatch_process.py ===")

# === Retrieve Unprocessed Cases ===
cursor.execute("""
    SELECT TOP 1000
        c.id as case_id,
        c.case_number,
        c.case_name,
        c.fk_court as court_code,
        o.fk_county as county_code
    FROM docketwatch.dbo.cases c
    left JOIN docketwatch.dbo.courts o ON c.fk_court = o.court_code
    WHERE status = 'Review'
      AND c.id not IN (SELECT fk_case FROM docketwatch.dbo.case_parties)
    ORDER BY c.id DESC
""")
cases = cursor.fetchall()

for row in cases:
    case_id, case_number, case_name, court_code, county_code = row
    try:
        log_message("INFO", f"Processing case {case_number}: {case_name}")
        process_case(case_id, case_number, case_name, court_code, county_code)
        check_celebrity_matches()

        cursor.execute("UPDATE docketwatch.dbo.cases SET case_parties_checked = 1 WHERE id = ?", (case_id,))
        conn.commit()
        log_message("INFO", f"Successfully processed case {case_id}")

    except Exception as e:
        log_message("ERROR", f"Error processing case {case_id}: {e}")

cursor.close()
conn.close()
# log_message("INFO", "=== Completed docketwatch_process.py ===")
