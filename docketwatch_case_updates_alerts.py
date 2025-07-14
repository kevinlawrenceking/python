import logging
from scraper_base import (
    get_db_cursor,
    init_logging_and_filename,
    create_case_update_if_needed,
    summarize_case_update_old,
    send_case_update_alert,
    log_message
)

def find_recent_case_ids(cursor, fk_task_run=None):
    log_message(cursor, fk_task_run, "INFO", "Running find_recent_case_ids query")
    cursor.execute("""
    SELECT DISTINCT top 1 c.id as case_id
    FROM docketwatch.dbo.case_events e
    INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
    WHERE e.emailed = 0 and
    CONVERT(date, e.event_date) >= CONVERT(date, DATEADD(day, -7, GETDATE()))
 
    AND e.stage_completed = 5
    """)
    case_ids = [row.case_id for row in cursor.fetchall()]
    log_message(cursor, fk_task_run, "INFO", f"Identified {len(case_ids)} recent case_ids to check: {case_ids}")
    return case_ids

def process_case_update(cursor, case_id, fk_task_run=None):
    log_message(cursor, fk_task_run, "INFO", f"Starting process_case_update for case_id {case_id}")
    update_id, event_ids = create_case_update_if_needed(cursor, case_id)
    if not update_id:
        log_message(cursor, fk_task_run, "INFO", f"No new update needed for case_id {case_id}")
        return False

    log_message(cursor, fk_task_run, "INFO", f"Created case_update {update_id} with {len(event_ids)} events")
    log_message(cursor, fk_task_run, "DEBUG", f"Event IDs: {event_ids}")

    ap, tmz_html, is_story = summarize_case_update_old(cursor, update_id)
    if not (ap and tmz_html):
        log_message(cursor, fk_task_run, "ERROR", f"Summarization failed for case_update {update_id}")
        return False

    email_result = send_case_update_alert(cursor, update_id)
    if email_result:
        log_message(cursor, fk_task_run, "INFO", f"Alert sent for case_update {update_id} (storyworthy: {is_story})")
    else:
        log_message(cursor, fk_task_run, "ERROR", f"Failed to send alert for case_update {update_id}")

    return True

def main():
    script_name = init_logging_and_filename()
    conn, cursor = get_db_cursor()

    cursor.execute("""
        SELECT TOP 1 r.id
        FROM docketwatch.dbo.task_runs r
        INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
        WHERE s.filename = 'run_case_update_summary.py'
        ORDER BY r.id DESC
    """)
    row = cursor.fetchone()
    fk_task_run = row[0] if row else None

    try:
        case_ids = find_recent_case_ids(cursor, fk_task_run)
        log_message(cursor, fk_task_run, "INFO", f"Found {len(case_ids)} cases to evaluate for updates")

        for cid in case_ids:
            try:
                log_message(cursor, fk_task_run, "INFO", f"Processing case_id: {cid}")
                process_case_update(cursor, cid, fk_task_run=fk_task_run)
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Error processing case {cid}: {e}")
    finally:
        cursor.close()
        conn.close()
        log_message(cursor, fk_task_run, "INFO", "Case update summary script complete.")

if __name__ == "__main__":
    main()
