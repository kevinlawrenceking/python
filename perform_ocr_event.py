import os, sys, argparse, traceback
import pyodbc
from perform_ocr_for_pdf import ocr_pdf_file  
from scraper_base import get_db_cursor, log_message

DOCS_ROOT = r"\\10.146.176.84\general\docketwatch\docs"


def get_pending_ocr_docs(cursor, case_event_id):
    cursor.execute("""
        SELECT d.doc_uid, d.rel_path
        FROM docketwatch.dbo.documents d
        WHERE d.fk_case_event = ?
          AND d.ocr_text IS NULL
          AND d.rel_path IS NOT NULL
    """, (case_event_id,))
    return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser(description="Perform OCR on PDFs linked to a case_event")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_event")
    args = parser.parse_args()

    conn, cursor = get_db_cursor()
    doc_count = 0

    try:
        docs = get_pending_ocr_docs(cursor, args.case_event_id)
        for row in docs:
            doc_uid, rel_path = row.doc_uid, row.rel_path
            abs_path = os.path.join(DOCS_ROOT, rel_path)
            if not os.path.exists(abs_path):
                log_message(cursor, None, "WARNING", f"File not found: {abs_path}")
                continue

            try:
                ocr_result = ocr_pdf_file(abs_path)
                if ocr_result and ocr_result.get("text"):
                    cursor.execute("""
                        UPDATE docketwatch.dbo.documents
                        SET ocr_text = ?, ocr_text_raw = ?, date_ocr_processed = GETDATE()
                        WHERE doc_uid = ?
                    """, (ocr_result["text"], ocr_result.get("raw", ""), doc_uid))
                    doc_count += 1
            except Exception as ex:
                log_message(cursor, None, "ERROR", f"OCR failed for {rel_path}: {str(ex)}")

        conn.commit()
        print(f"Completed OCR for {doc_count} documents.")

    except Exception as e:
        traceback.print_exc()
        log_message(cursor, None, "ERROR", f"Unhandled error in OCR script: {str(e)}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
