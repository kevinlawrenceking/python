from scraper_base import get_db_cursor
from pacer_case_event_pdf_summarizer import process_single_pdf
import time

def main():
    conn, cur = get_db_cursor()
    cur.execute("""
        SELECT doc_uid 
        FROM docketwatch.dbo.documents 
        WHERE pdf_type = 'Docket'
    """)
    rows = cur.fetchall()
    print(f"Processing {len(rows)} records...")

    for i, row in enumerate(rows):
        uid = str(row[0])
        print(f"\n[{i+1}/{len(rows)}] Processing {uid}")
        try:
            process_single_pdf(uid)
        except Exception as e:
            print(f"Error on {uid}: {e}")
        time.sleep(2)  # short pause between calls

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
