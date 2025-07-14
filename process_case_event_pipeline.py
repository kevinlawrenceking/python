# process_case_event_pipeline.py

import os
import logging
from scraper_base import (
    get_db_cursor,
    insert_documents_for_event,
    download_pending_documents_for_event,
    perform_ocr_for_documents,
    generate_ai_summary_for_documents
)

DOCS_ROOT = r"\\10.146.176.84\general\docketwatch\docs"

# --- Logging Setup ---
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{SCRIPT_NAME}.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def process_case_event(event_id, cursor):
    logging.info(f"Processing case_event_id: {event_id}")

    # 1. Insert documents if missing
    inserted_count = insert_documents_for_event(cursor, event_id)
    if inserted_count > 0:
        logging.info(f"Inserted {inserted_count} document(s) for event {event_id}")
    else:
        logging.info(f"No new documents to insert for event {event_id}")

    # 2. Download any documents marked as 'pending'
    downloaded_count = download_pending_documents_for_event(cursor, event_id)
    if downloaded_count > 0:
        logging.info(f"Downloaded {downloaded_count} PDF(s) for event {event_id}")
    else:
        logging.info(f"No pending PDFs to download for event {event_id}")

    # 3. Perform OCR for documents without ocr_text
    ocr_count = perform_ocr_for_documents(cursor, event_id, DOCS_ROOT)
    if ocr_count > 0:
        logging.info(f"OCR completed for {ocr_count} document(s) in event {event_id}")
    else:
        logging.info(f"No OCR needed for event {event_id}")

    # 4. Generate Gemini AI summaries for OCR'd documents without summary
    summary_count = generate_ai_summary_for_documents(cursor, event_id, DOCS_ROOT)
    if summary_count > 0:
        logging.info(f"Generated AI summaries for {summary_count} document(s) in event {event_id}")
    else:
        logging.info(f"No AI summaries needed for event {event_id}")

def get_unprocessed_case_events(cursor):
    """
    Returns all case_event IDs that have not been emailed yet.
    Later we may scope this by portal, tool_id, or cutoff date.
    """
    cursor.execute("""
        SELECT id
        FROM docketwatch.dbo.case_events
        WHERE emailed = 0
        ORDER BY created_at ASC
    """)
    return [row.id for row in cursor.fetchall()]

def main():
    conn, cursor = get_db_cursor()
    try:
        event_ids = get_unprocessed_case_events(cursor)
        logging.info(f"Found {len(event_ids)} case events to process.")
        for event_id in event_ids:
            try:
                process_case_event(event_id, cursor)
            except Exception as e:
                logging.error(f"Error processing event {event_id}: {e}")
        conn.commit()
    finally:
        cursor.close()
        conn.close()
        logging.info("All case events processed.")

if __name__ == "__main__":
    main()
