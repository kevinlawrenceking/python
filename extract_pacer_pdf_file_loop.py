import pyodbc
import subprocess
import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('u:/docketwatch/python/logs/extract_pacer_pdf_file_loop.log'),
        logging.StreamHandler()
    ]
)

while True:
    try:
        # Database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()

        # Query to find applicable case_event IDs 
        # Include all case events created today, but if documents exist, only where rel_path = 'pending'
        cursor.execute("""
        SELECT distinct TOP 3 e.[id] AS case_id, e.created_at
        FROM [docketwatch].[dbo].[case_events] e 
        INNER JOIN [docketwatch].[dbo].[cases] c ON c.id = e.fk_cases
        LEFT JOIN [docketwatch].[dbo].[documents] d ON d.fk_case_event = e.id
        WHERE c.fk_tool = 2 and e.emailed <> 1
            AND CAST(e.created_at AS DATE) = CAST(GETDATE() AS DATE)
            AND (d.fk_case_event IS NULL)
        ORDER BY e.created_at DESC
        """)

        case_ids = [row.case_id for row in cursor.fetchall()]
        logging.info(f"Found {len(case_ids)} case_events to process at {datetime.now()}")
        print(f"Found {len(case_ids)} case_events to process.")

        for case_id in case_ids:
            logging.info(f"Starting processing for case_event ID: {case_id}")
            print(f"Running for case_event ID: {case_id}")
            try:
                # Run with timeout and capture output for better debugging
                result = subprocess.run(
                    ["python", "u:\\docketwatch\\python\\process_pacer_event_pdf.py", str(case_id)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per case
                )
                logging.info(f"Successfully completed case_id {case_id}")
                print(f"Success for case_id {case_id}")
                if result.stdout:
                    print(f"Output: {result.stdout.strip()}")
                
                # Longer delay between processes to avoid PACER session conflicts
                time.sleep(5)
                
            except subprocess.CalledProcessError as e:
                error_msg = f"Error running process_pacer_event_pdf.py for case_id {case_id}: {e}"
                logging.error(error_msg)
                print(error_msg)
                if e.stdout:
                    logging.error(f"STDOUT: {e.stdout}")
                    print(f"STDOUT: {e.stdout}")
                if e.stderr:
                    logging.error(f"STDERR: {e.stderr}")
                    print(f"STDERR: {e.stderr}")
            except subprocess.TimeoutExpired as e:
                timeout_msg = f"Timeout for case_id {case_id} after 5 minutes"
                logging.warning(timeout_msg)
                print(timeout_msg)
            except Exception as e:
                unexpected_msg = f"Unexpected error for case_id {case_id}: {e}"
                logging.error(unexpected_msg)
                print(unexpected_msg)

    except Exception as e:
        print(f"Unexpected error: {e}")

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

    print("Sleeping for 60 seconds...\n")
    time.sleep(60)
