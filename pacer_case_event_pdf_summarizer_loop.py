import pyodbc
import time
from pacer_case_event_pdf_summarizer import process_single_pdf

def get_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn, conn.cursor()

def main():
    while True:
        conn, cur = get_cursor()
        cur.execute("""
            SELECT TOP 10 doc_uid
            FROM docketwatch.dbo.documents
            WHERE summary_ai IS NULL AND pdf_type IS NOT NULL
              AND rel_path <> 'pending'
            ORDER BY date_downloaded DESC
        """)
        rows = cur.fetchall()
        print(f"Found {len(rows)} PDFs to summarize...")

        for row in rows:
            doc_uid = str(row[0])
            print(f"\n--- Processing {doc_uid} ---")
            try:
                process_single_pdf(doc_uid)
            except Exception as e:
                print(f"Error processing {doc_uid}: {e}")

        cur.close()
        conn.close()
        print("Sleeping for 60 seconds...\n")
        time.sleep(60)

if __name__ == "__main__":
    main()
