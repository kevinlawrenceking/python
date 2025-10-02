import pyodbc
import subprocess
import time
import logging
import os
from datetime import datetime

# Ensure logs directory exists
log_dir = 'u:/docketwatch/python/logs'
os.makedirs(log_dir, exist_ok=True)

# Get the script filename without extension for log naming
script_name = os.path.splitext(os.path.basename(__file__))[0]
log_file = f'{log_dir}/{script_name}.log'

# Setup logging with error handling
try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.info(f"Logging initialized successfully - {log_file}")
except Exception as e:
    print(f"Failed to setup logging: {e}")
    # Fallback to console only
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("Starting PACER PDF extraction loop...")

# Test if we can connect to database first
try:
    test_conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    test_cursor = test_conn.cursor()
    test_cursor.execute("SELECT 1")
    test_conn.close()
    logging.info("Database connectivity test passed")
    print("Database connectivity test passed")
except Exception as test_error:
    logging.error(f"Database connectivity test failed: {test_error}")
    print(f"Database connectivity test failed: {test_error}")
    exit(1)

while True:
    try:
        logging.info("Starting new iteration of PDF extraction loop")
        print("Starting new iteration...")
        
        # Database connection
        try:
            conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
            cursor = conn.cursor()
            logging.info("Database connection established")
        except Exception as db_error:
            logging.error(f"Database connection failed: {db_error}")
            print(f"Database connection failed: {db_error}")
            time.sleep(60)
            continue

        # Query to find applicable case_event IDs 
        # Include all case events created today, but if documents exist, only where rel_path = 'pending'
        try:
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
            logging.info("Query executed successfully")
        except Exception as query_error:
            logging.error(f"Query execution failed: {query_error}")
            print(f"Query execution failed: {query_error}")
            cursor.close()
            conn.close()
            time.sleep(60)  
            continue

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
        error_msg = f"Unexpected error in main loop: {e}"
        logging.error(error_msg)
        print(error_msg)
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")

    finally:
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except Exception as cleanup_error:
            logging.warning(f"Error during cleanup: {cleanup_error}")

    logging.info("Sleeping for 60 seconds...")
    print("Sleeping for 60 seconds...\n")
    time.sleep(60)
