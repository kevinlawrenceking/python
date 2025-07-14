import time
import sys
import pyodbc

# Add script directory to path so Python can find send_pdf_summary_email.py
sys.path.append(r"U:\docketwatch\python")

from email_pdf_summary import send_summary_email  # Import your email sender

DSN = "Docketwatch"

def main():
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    cur = conn.cursor()

    cur.execute("""
        SELECT doc_uid 
        FROM docketwatch.dbo.documents 
        WHERE summary_ai_html IS NOT NULL 
          AND summary_email_sent_at IS NULL
    """)
    rows = cur.fetchall()
    print(f"Processing {len(rows)} records...")

    for i, row in enumerate(rows):
        doc_uid = str(row[0])
        print(f"\n[{i+1}/{len(rows)}] Processing {doc_uid}")

        try:
            send_summary_email(doc_uid)
            cur.execute("""
                UPDATE docketwatch.dbo.documents
                SET summary_email_sent_at = GETDATE()
                WHERE doc_uid = ?
            """, (doc_uid,))
            conn.commit()
        except Exception as e:
            print(f"Error sending summary for {doc_uid}: {e}")

        time.sleep(2)  # Pause between sends

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
