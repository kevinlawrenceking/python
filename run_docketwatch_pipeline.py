import logging
import subprocess
from scraper_base import (
    get_db_cursor,
    log_message,
    perform_ocr_for_documents,
    generate_ai_summary_for_documents
)

DOCS_ROOT       = r"\\10.146.176.84\general\docketwatch\docs"
LOG_FILE        = r"\\10.146.176.84\general\docketwatch\python\logs\run_docketwatch_pipeline.log"
EXTRACT_SCRIPT  = r"U:\\docketwatch\\python\\extract_pacer_pdf_metadata.py"
PDF_SCRIPT      = r"U:\\docketwatch\\python\\process_pacer_event_pdf.py"
FINALIZE_SCRIPT = r"U:\\docketwatch\\python\\summarize_case_event_ai.py"
CASE_SUMMARIZER = r"U:\\docketwatch\\python\\pacer_case_summarizer.py"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def process_all_case_events(cursor, fk_task_run=None):
    cursor.execute("""
        SELECT TOP 10 e.id
        FROM docketwatch.dbo.case_events e
        JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
        WHERE c.fk_tool = 2 AND e.stage_completed < 5 
        ORDER BY e.created_at DESC
    """)
    event_ids = [row.id for row in cursor.fetchall()]
    log_message(cursor, fk_task_run, "INFO", f"Found {len(event_ids)} case_events to process")

    for event_id in event_ids:
        log_message(cursor, fk_task_run, "INFO", f"Processing case_event_id: {event_id}")

        # Step 0: Ensure case-level summary exists
        cursor.execute("""
            SELECT c.id, c.summarize
            FROM docketwatch.dbo.cases c
            JOIN docketwatch.dbo.case_events e ON e.fk_cases = c.id
            WHERE e.id = ?
        """, (event_id,))
        case_row = cursor.fetchone()
        case_id, case_summary = case_row if case_row else (None, None)

        if case_id and not case_summary:
            try:
                subprocess.run([
                    "python", CASE_SUMMARIZER, "--case-id", str(case_id)
                ], capture_output=True, text=True, timeout=180)
                log_message(cursor, fk_task_run, "INFO", f"Case summary triggered for case_id {case_id}")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Case summary subprocess failed for {case_id}: {e}")

        # Get current stage
        cursor.execute("SELECT stage_completed FROM docketwatch.dbo.case_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        stage_completed = row[0] if row else 0

        # Stage 1: Extract metadata
        if stage_completed < 1:
            try:
                result = subprocess.run(["python", EXTRACT_SCRIPT, str(event_id)], capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    log_message(cursor, fk_task_run, "INFO", f"Stage 1 success for {event_id}")
                    cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 1 WHERE id = ?", (event_id,))
                    cursor.connection.commit()
                else:
                    log_message(cursor, fk_task_run, "ERROR", f"Stage 1 failed for {event_id}: {result.stderr}")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Stage 1 exception for {event_id}: {e}")

        # Stage 2: Download PDFs
        if stage_completed < 2:
            try:
                result = subprocess.run(["python", PDF_SCRIPT, str(event_id)], capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    log_message(cursor, fk_task_run, "INFO", f"Stage 2 success for {event_id}")
                    cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 2 WHERE id = ?", (event_id,))
                    cursor.connection.commit()
                else:
                    log_message(cursor, fk_task_run, "ERROR", f"Stage 2 failed for {event_id}: {result.stderr}")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Stage 2 exception for {event_id}: {e}")

        # Stage 3: OCR
        if stage_completed < 3:
            try:
                ocred = perform_ocr_for_documents(cursor, event_id, DOCS_ROOT)
                log_message(cursor, fk_task_run, "INFO", f"Stage 3 (OCR) {event_id}: {ocred} pages")
                if ocred > 0:
                    cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 3 WHERE id = ?", (event_id,))
                    cursor.connection.commit()
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Stage 3 exception for {event_id}: {e}")

        # Stage 4: Document-level summaries
        if stage_completed < 4:
            try:
                summarized = generate_ai_summary_for_documents(cursor, event_id, DOCS_ROOT)
                log_message(cursor, fk_task_run, "INFO", f"Stage 4 (AI DOC) {event_id}: {summarized} summaries")
                if summarized > 0:
                    cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 4 WHERE id = ?", (event_id,))
                    cursor.connection.commit()
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Stage 4 exception for {event_id}: {e}")

        # Stage 5: Case event-level summary
        if stage_completed < 5:
            try:
                result = subprocess.run(["python", FINALIZE_SCRIPT, str(event_id)], capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    log_message(cursor, fk_task_run, "INFO", f"Stage 5 (FINALIZE) complete for {event_id}")
                    cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 5 WHERE id = ?", (event_id,))
                    cursor.connection.commit()
                else:
                    log_message(cursor, fk_task_run, "ERROR", f"Stage 5 failed for {event_id}: {result.stderr}")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Stage 5 exception for {event_id}: {e}")

def main():
    conn, cursor = get_db_cursor()
    cursor.execute("""
        SELECT TOP 1 r.id
        FROM docketwatch.dbo.task_runs r
        INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
        WHERE s.filename = 'run_docketwatch_pipeline.py'
        ORDER BY r.id DESC
    """)
    row = cursor.fetchone()
    fk_task_run = row[0] if row else None

    try:
        process_all_case_events(cursor, fk_task_run=fk_task_run)
    finally:
        cursor.close()
        conn.close()
        log_message(None, fk_task_run, "INFO", "Pipeline run complete.")

if __name__ == "__main__":
    main()
