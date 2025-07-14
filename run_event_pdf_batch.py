import pyodbc
import subprocess
import time
import logging

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

while True:
    try:
        # --- Database Connection ---
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()

        # --- Ensure arr_de_seq_nums is populated ---
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET arr_de_seq_nums = 
                SUBSTRING(
                    event_url,
                    CHARINDEX('de_seq_num=', event_url) + 11,
                    CHARINDEX('&', event_url + '&', CHARINDEX('de_seq_num=', event_url)) 
                    - CHARINDEX('de_seq_num=', event_url) - 11
                )
            WHERE event_url IS NOT NULL
              AND arr_de_seq_nums IS NULL
              AND event_url LIKE '%de_seq_num%'
        """)
        conn.commit()

        # --- Get Case Events Missing Document Records ---
        cursor.execute("""
            SELECT top 10 id
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
        logging.info(f"Found {len(case_ids)} unprocessed case_events.")

        # --- Run the Merged PACER Processor ---
        for i, case_id in enumerate(case_ids):
            logging.info(f"[{i+1}/{len(case_ids)}] Running process_pacer_event_pdf.py for case_event ID: {case_id}")
            try:
                subprocess.run([
                    "python",
                    "u:\\docketwatch\\python\\process_pacer_event_pdf.py",
                    str(case_id)
                ], check=True)
                time.sleep(2)
            except subprocess.CalledProcessError as e:
                logging.error(f"Script failed for case_event {case_id}: {e}")

    except Exception as e:
        logging.error(f"Unhandled error: {e}")

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

    logging.info("Sleeping for 60 seconds...\n")
    time.sleep(60)
