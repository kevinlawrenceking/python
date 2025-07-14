
import logging, traceback
from scraper_base import get_db_cursor

logging.basicConfig(
    filename=r'U:\docketwatch\python\logs\backfill_case_event_stages.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def backfill_stages():
    conn, cursor = get_db_cursor()
    logging.info("Starting case_event stage backfill")

    cursor.execute("SELECT id FROM docketwatch.dbo.case_events")
    ids = [row.id for row in cursor.fetchall()]
    logging.info(f"Found {len(ids)} case_events")

    stage_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}

    for i, event_id in enumerate(ids):
        try:
            # Stage 5 check
            cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.case_events WHERE id = ? AND LEN(summarize) > 20", event_id)
            if cursor.fetchone()[0]:
                cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 5 WHERE id = ?", event_id)
                stage_counts[5] += 1
            # Stage 4 check
            elif cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE fk_case_event = ? AND summary_ai IS NOT NULL", event_id).fetchone()[0]:
                cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 4 WHERE id = ?", event_id)
                stage_counts[4] += 1
            # Stage 3 check
            elif cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE fk_case_event = ? AND ocr_text IS NOT NULL", event_id).fetchone()[0]:
                cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 3 WHERE id = ?", event_id)
                stage_counts[3] += 1
            # Stage 2 check
            elif cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE fk_case_event = ? AND rel_path IS NOT NULL", event_id).fetchone()[0]:
                cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 2 WHERE id = ?", event_id)
                stage_counts[2] += 1
            else:
                cursor.execute("UPDATE docketwatch.dbo.case_events SET stage_completed = 1 WHERE id = ?", event_id)
                stage_counts[1] += 1

            if i % 500 == 0:
                conn.commit()
                logging.info(f"Processed {i} / {len(ids)} events")

        except Exception as e:
            logging.error(f"Error on case_event {event_id}: {e}")
            logging.error(traceback.format_exc())

    conn.commit()
    logging.info("Backfill complete.")
    for stage, count in stage_counts.items():
        logging.info(f"Stage {stage}: {count} records")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    backfill_stages()
