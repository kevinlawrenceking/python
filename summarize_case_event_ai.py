import sys
import pyodbc
import markdown2
import logging
import google.generativeai as genai

from scraper_base import get_db_cursor, log_message


def summarize_case_event(event_id):
    conn, cursor = get_db_cursor()

    try:
        # Load API key and configure Gemini
        cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        if not row or not row[0]:
            logging.error("Gemini API key not found.")
            return

        genai.configure(api_key=row[0])
        model = genai.GenerativeModel("gemini-2.5-pro")

        # Get documents linked to this event
        cursor.execute("""
            SELECT d.summary_ai
            FROM docketwatch.dbo.documents d
            WHERE d.fk_case_event = ? AND d.summary_ai IS NOT NULL AND LEN(d.summary_ai) > 10
            ORDER BY d.date_downloaded
        """, (event_id,))
        docs = [row.summary_ai for row in cursor.fetchall()]
        if not docs:
            logging.info("No summarized documents for event.")
            return

        # Get context
        cursor.execute("""
            SELECT e.event_description, e.event_date, c.summarize
            FROM docketwatch.dbo.case_events e
            JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            WHERE e.id = ?
        """, (event_id,))
        row = cursor.fetchone()
        if not row:
            logging.error("Event not found.")
            return

        event_desc, event_date, case_summary = row

        # Build prompt
        prompt = f"""
SYSTEM: You are a legal summarizer.
Your task is to summarize what happened in this court event.
Do not speculate, evaluate, or write an article. Just summarize the filings.

--- CASE CONTEXT ---
{case_summary or '[No case summary provided]'}

--- EVENT INFO ---
Date: {event_date}
Description: {event_desc}

--- DOCUMENT SUMMARIES ---
{chr(10).join(docs)[:12000]}
"""

        # Generate response
        response = model.generate_content(prompt[:16000])
        text_output = response.text.strip()
        html_output = markdown2.markdown(text_output)

        # Save
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET summarize = ?, summarize_html = ?, ai_processed_at = GETDATE()
            WHERE id = ?
        """, (text_output, html_output, event_id))
        conn.commit()
        logging.info(f"[FINALIZE] Saved summary for case_event {event_id}")

    except Exception as e:
        logging.error(f"[FINALIZE] Exception: {e}")
        log_message(cursor, None, "ERROR", f"Final summary failed for event {event_id}: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python summarize_case_event_ai.py <case_event_id>")
        sys.exit(1)
    summarize_case_event(sys.argv[1])