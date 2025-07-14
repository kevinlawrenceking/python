import pyodbc
import subprocess
import time

while True:
    try:
        # Database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()

        # Query to find applicable case_event IDs
        cursor.execute("""
        SELECT DISTINCT TOP 10 e.[id] AS case_id, created_at
        FROM [docketwatch].[dbo].[case_events] e 
        INNER JOIN [docketwatch].[dbo].[documents] d ON d.fk_case_event = e.id
        WHERE d.fk_case_event IS NOT NULL AND d.rel_path = 'pending'
        ORDER BY created_at DESC
        """)

        case_ids = [row.case_id for row in cursor.fetchall()]
        print(f"Found {len(case_ids)} case_events to process.")

        for case_id in case_ids:
            print(f"Running for case_event ID: {case_id}")
            try:
                subprocess.run(
                    ["python", "u:\\docketwatch\\python\\extract_pacer_pdf_file.py", str(case_id)],
                    check=True
                )
                time.sleep(2)  # slight delay between each subprocess
            except subprocess.CalledProcessError as e:
                print(f"Error running extract_pacer_pdf_file.py for case_id {case_id}: {e}")

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
