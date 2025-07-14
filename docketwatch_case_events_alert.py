import pyodbc
import subprocess
import logging
import os
from datetime import datetime

# Setup logging
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
DSN = "Docketwatch"
SCRIPT_PATH = r"\\10.146.176.84\general\docketwatch\python\docketwatch_case_events_alert_plus2.py"

def run_case_update(case_id):
    try:
        logging.info(f"Running case update for case_id {case_id}")
        subprocess.run(["python", SCRIPT_PATH, str(case_id)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to process case_id {case_id}: {e}")
        return False

def main():
    try:
        conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
        cursor = conn.cursor()

        # Get case_ids with unemailed events today
        cursor.execute("""
            SELECT DISTINCT  c.id as case_id
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE CONVERT(date, e.event_date) >= CONVERT(date, DATEADD(day, -7, GETDATE()))
            AND e.emailed = 0 
        """)
        case_ids = [row.case_id for row in cursor.fetchall()]

        if not case_ids:
            logging.info("No unemailed case events today.")
            return

        for case_id in case_ids:
            if run_case_update(case_id):
                # Mark events as emailed for that case
                cursor.execute("""
                    UPDATE docketwatch.dbo.case_events
                    SET emailed = 1
                    WHERE fk_cases = ? AND emailed = 0
                """, (case_id,))
                conn.commit()
                logging.info(f"Marked events as emailed for case_id {case_id}")

        cursor.close()
        conn.close()
        logging.info("All case updates processed.")
    except Exception as e:
        logging.error(f"Runner script failed: {e}")

if __name__ == "__main__":
    main()
