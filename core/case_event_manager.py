"""
Case Event Manager for DocketWatch
==================================

This module handles all case and case event related operations including:
- Creating and updating case records
- Managing case events lifecycle
- Handling case status tracking (found/not found)
- Case event assignment and organization

Extracted from scraper_base.py to create focused, reusable components.
"""

import uuid
import logging
from datetime import datetime

# === Case Status Management ===

def mark_case_found(cursor, case_id):
    """
    Reset not_found status when a previously missing case is found.
    
    Args:
        cursor: Database cursor
        case_id: ID of the case that was found
    """
    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET
            not_found_count = 0,
            not_found_flag = 0,
            last_not_found = NULL,
            last_found = GETDATE()
        WHERE id = ?
    """, (case_id,))
    cursor.connection.commit()
    logging.info(f"Case {case_id} marked as found - reset not_found status")

def mark_case_not_found(cursor, case_id, fk_task_run=None, threshold=3):
    """
    Increment not_found count and set flag when threshold is reached.
    
    Args:
        cursor: Database cursor
        case_id: ID of the case that wasn't found
        fk_task_run: Optional task run ID for logging
        threshold: Number of failures before flagging (default 3)
        
    Returns:
        dict: Status information including count and whether threshold was reached
    """
    # Update the case record
    cursor.execute("""
        UPDATE docketwatch.dbo.cases
        SET 
            not_found_count = ISNULL(not_found_count, 0) + 1,
            last_not_found = GETDATE(),
            not_found_flag = CASE 
                                WHEN ISNULL(not_found_count, 0) + 1 >= ? THEN 1
                                ELSE 0
                             END
        WHERE id = ?
    """, (threshold, case_id))
    cursor.connection.commit()

    # Get the updated count for reporting
    cursor.execute("""
        SELECT not_found_count, last_not_found, not_found_flag 
        FROM docketwatch.dbo.cases 
        WHERE id = ?
    """, (case_id,))
    
    row = cursor.fetchone()
    if not row:
        return {'error': 'Case not found in database'}
    
    count, last_checked, is_flagged = row
    threshold_reached = count >= threshold
    
    # Log the appropriate message
    if threshold_reached:
        log_case_message(cursor, fk_task_run, "ALERT", 
                        f"Case ID {case_id} could not be found {count} times and is now flagged as not found.", 
                        case_id)
    else:
        log_case_message(cursor, fk_task_run, "WARNING", 
                        f"Case ID {case_id} was not found (failure count: {count}).", 
                        case_id)
    
    return {
        'case_id': case_id,
        'failure_count': count,
        'threshold_reached': threshold_reached,
        'is_flagged': bool(is_flagged),
        'last_checked': last_checked
    }

# === Case Record Management ===

def update_case_records(cursor, case_id, case_number, case_name, tool_id, fk_court, case_type, fk_task_run, current_url):
    """
    Update master case record with current information.
    
    Args:
        cursor: Database cursor
        case_id: Case ID to update
        case_number: Case number
        case_name: Case name/title
        tool_id: ID of the tool that updated this
        fk_court: Court ID
        case_type: Type of case
        fk_task_run: Task run ID
        current_url: Current URL for the case
    """
    try:
        # Update master case record
        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET
                case_number = ?,
                case_name = ?,
                fk_tool = ?,
                status = 'Tracked',
                fk_court = ?,
                case_type = ?,
                fk_task_run_log = ?,
                case_url = ?,
                is_tracked = 1,
                last_updated = GETDATE()
            WHERE id = ?
        """, (case_number, case_name, tool_id, fk_court, case_type, fk_task_run, current_url, case_id))
        
        cursor.connection.commit()
        
        log_case_message(cursor, fk_task_run, "INFO", 
                        f"Updated case {case_number} ({case_name}).", case_id)
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to update case {case_id}: {e}")
        log_case_message(cursor, fk_task_run, "ERROR", 
                        f"Failed to update case {case_id}: {e}", case_id)
        return False

def create_case_if_not_exists(cursor, case_number, case_name, court_id, tool_id, case_url=None):
    """
    Create a new case record if it doesn't already exist.
    
    Args:
        cursor: Database cursor
        case_number: Case number
        case_name: Case name/title
        court_id: Court ID
        tool_id: Tool that created this case
        case_url: Optional URL for the case
        
    Returns:
        str: Case ID (existing or newly created)
    """
    # Check if case already exists
    cursor.execute("""
        SELECT id FROM docketwatch.dbo.cases 
        WHERE case_number = ? AND fk_court = ?
    """, (case_number, court_id))
    
    existing = cursor.fetchone()
    if existing:
        return existing.id
    
    # Create new case
    case_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO docketwatch.dbo.cases (
            id, case_number, case_name, fk_court, fk_tool, 
            case_url, status, is_tracked, created_at, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, 'Tracked', 1, GETDATE(), GETDATE())
    """, (case_id, case_number, case_name, court_id, tool_id, case_url))
    
    cursor.connection.commit()
    logging.info(f"Created new case: {case_number} ({case_id})")
    
    return case_id

# === Case Event Management ===

def insert_new_case_events(cursor, fk_case, events, fk_task_run):
    """
    Insert new case events, avoiding duplicates.
    
    Args:
        cursor: Database cursor
        fk_case: Case ID
        events: List of tuples (event_date, description, extra_info)
        fk_task_run: Task run ID for logging
        
    Returns:
        int: Number of new events inserted
    """
    if not events:
        return 0
    
    inserted = 0
    
    for event_date, description, extra in events:
        # Check if event already exists
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_description = ? AND event_date = ?
        """, (fk_case, description, event_date))
        
        if cursor.fetchone()[0] == 0:
            # Insert new event
            event_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_events (
                    id, fk_cases, event_date, event_description,
                    additional_information, fk_task_run_log, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, GETDATE())
            """, (event_id, fk_case, event_date, description, extra, fk_task_run))
            inserted += 1
    
    cursor.connection.commit()
    
    # Log the results
    log_type = "ALERT" if inserted > 0 else "INFO"
    log_case_message(cursor, fk_task_run, log_type, 
                    f"Inserted {inserted} new event(s) for case ID {fk_case}", fk_case)
    
    return inserted

def create_case_update_if_needed(cursor, case_id):
    """
    Create a new case_update if unassigned, unemailed events exist.
    Assigns those events to the new update.
    
    Args:
        cursor: Database cursor
        case_id: Case ID to check for events
        
    Returns:
        tuple: (update_id, list_of_event_ids) or (None, []) if no events found
    """
    # Find unemailed, unassigned events for this case
    cursor.execute("""
        SELECT id
        FROM docketwatch.dbo.case_events
        WHERE fk_cases = ? AND emailed = 0 AND fk_case_update IS NULL
        ORDER BY created_at ASC
    """, (case_id,))
    
    rows = cursor.fetchall()
    if not rows:
        return None, []

    event_ids = [row.id for row in rows]

    # Create new case_update
    update_id = str(uuid.uuid4())
    now = datetime.now()

    cursor.execute("""
        INSERT INTO docketwatch.dbo.case_updates (
            id, fk_case, created_at
        ) VALUES (?, ?, ?)
    """, (update_id, case_id, now))

    # Assign each event to this case_update
    for event_id in event_ids:
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET fk_case_update = ?
            WHERE id = ?
        """, (update_id, event_id))

    cursor.connection.commit()
    
    logging.info(f"Created case_update {update_id} with {len(event_ids)} events for case {case_id}")
    
    return update_id, event_ids

def get_case_events_for_update(cursor, case_update_id):
    """
    Get all events associated with a case update.
    
    Args:
        cursor: Database cursor
        case_update_id: Case update ID
        
    Returns:
        list: List of event records
    """
    cursor.execute("""
        SELECT 
            e.id,
            e.event_date,
            e.event_description,
            e.additional_information,
            e.created_at
        FROM docketwatch.dbo.case_events e
        WHERE e.fk_case_update = ?
        ORDER BY e.event_date DESC, e.created_at DESC
    """, (case_update_id,))
    
    return cursor.fetchall()

# === Event Organization and Cleanup ===

def merge_duplicate_events(cursor, case_id, dry_run=True):
    """
    Identify and optionally merge duplicate events for a case.
    
    Args:
        cursor: Database cursor
        case_id: Case ID to check
        dry_run: If True, only identify duplicates without merging
        
    Returns:
        list: List of duplicate event groups found
    """
    cursor.execute("""
        SELECT 
            event_date,
            event_description,
            COUNT(*) as count,
            STRING_AGG(CAST(id AS VARCHAR(36)), ',') as event_ids
        FROM docketwatch.dbo.case_events
        WHERE fk_cases = ?
        GROUP BY event_date, event_description
        HAVING COUNT(*) > 1
    """, (case_id,))
    
    duplicates = cursor.fetchall()
    
    if not dry_run and duplicates:
        # Actually merge the duplicates (keep the oldest, remove others)
        for event_date, description, count, event_ids_str in duplicates:
            event_ids = event_ids_str.split(',')
            # Keep the first (oldest) event, delete the rest
            for event_id in event_ids[1:]:
                cursor.execute("""
                    DELETE FROM docketwatch.dbo.case_events
                    WHERE id = ?
                """, (event_id,))
        
        cursor.connection.commit()
        logging.info(f"Merged {len(duplicates)} duplicate event groups for case {case_id}")
    
    return duplicates

def archive_old_events(cursor, case_id, cutoff_date, dry_run=True):
    """
    Archive events older than a specified date.
    
    Args:
        cursor: Database cursor
        case_id: Case ID to process
        cutoff_date: Events older than this will be archived
        dry_run: If True, only count events without archiving
        
    Returns:
        int: Number of events that would be/were archived
    """
    cursor.execute("""
        SELECT COUNT(*)
        FROM docketwatch.dbo.case_events
        WHERE fk_cases = ? AND event_date < ?
    """, (case_id, cutoff_date))
    
    count = cursor.fetchone()[0]
    
    if not dry_run and count > 0:
        # Move to archive table (assuming it exists)
        cursor.execute("""
            INSERT INTO docketwatch.dbo.case_events_archive
            SELECT * FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_date < ?
        """, (case_id, cutoff_date))
        
        cursor.execute("""
            DELETE FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_date < ?
        """, (case_id, cutoff_date))
        
        cursor.connection.commit()
        logging.info(f"Archived {count} old events for case {case_id}")
    
    return count

# === Validation and Data Quality ===

def validate_event_data(event_date, description, additional_info=None):
    """
    Validate event data before insertion.
    
    Args:
        event_date: Event date
        description: Event description
        additional_info: Optional additional information
        
    Returns:
        tuple: (is_valid, error_message)
    """
    errors = []
    
    # Check required fields
    if not event_date:
        errors.append("Event date is required")
    
    if not description or len(description.strip()) < 5:
        errors.append("Event description must be at least 5 characters")
    
    # Check date format/validity
    if event_date:
        try:
            if isinstance(event_date, str):
                datetime.strptime(event_date, '%Y-%m-%d')
        except ValueError:
            errors.append("Invalid date format (expected YYYY-MM-DD)")
    
    # Check description length
    if description and len(description) > 1000:
        errors.append("Event description too long (max 1000 characters)")
    
    is_valid = len(errors) == 0
    error_message = "; ".join(errors) if errors else None
    
    return is_valid, error_message

def get_case_statistics(cursor, case_id=None):
    """
    Get statistics about cases and events.
    
    Args:
        cursor: Database cursor
        case_id: Optional case ID to filter by
        
    Returns:
        dict: Statistics dictionary
    """
    where_case = "WHERE c.id = ?" if case_id else ""
    params = [case_id] if case_id else []
    
    cursor.execute(f"""
        SELECT 
            COUNT(DISTINCT c.id) as total_cases,
            COUNT(e.id) as total_events,
            SUM(CASE WHEN c.not_found_flag = 1 THEN 1 ELSE 0 END) as flagged_cases,
            SUM(CASE WHEN e.emailed = 0 THEN 1 ELSE 0 END) as unemailed_events,
            SUM(CASE WHEN e.fk_case_update IS NULL THEN 1 ELSE 0 END) as unassigned_events
        FROM docketwatch.dbo.cases c
        LEFT JOIN docketwatch.dbo.case_events e ON c.id = e.fk_cases
        {where_case}
    """, params)
    
    row = cursor.fetchone()
    return {
        'total_cases': row.total_cases,
        'total_events': row.total_events,
        'flagged_cases': row.flagged_cases,
        'unemailed_events': row.unemailed_events,
        'unassigned_events': row.unassigned_events
    }

# === Utility Functions ===

def log_case_message(cursor, fk_task_run, log_type, message, fk_case=None):
    """
    Log a message to both the logging system and database.
    
    Args:
        cursor: Database cursor
        fk_task_run: Task run ID
        log_type: Type of log message (INFO, WARNING, ERROR, ALERT)
        message: Log message
        fk_case: Optional case ID
    """
    # Log to file
    logging.info(message)
    
    # Log to database if task run is available
    if cursor and fk_task_run:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.task_runs_log (
                    fk_task_run, log_timestamp, log_type, description, fk_case
                )
                OUTPUT INSERTED.id 
                VALUES (?, GETDATE(), ?, ?, ?)
            """, (fk_task_run, log_type, message, fk_case))
            cursor.connection.commit()
        except Exception as ex:
            logging.warning(f"Failed to write to task_runs_log: {ex}")

def get_cases_needing_attention(cursor, limit=100):
    """
    Get cases that need attention (not found, stale, etc.).
    
    Args:
        cursor: Database cursor
        limit: Maximum number of cases to return
        
    Returns:
        list: List of case records needing attention
    """
    cursor.execute(f"""
        SELECT TOP {limit}
            c.id,
            c.case_number,
            c.case_name,
            c.not_found_count,
            c.last_found,
            c.last_not_found,
            c.last_updated
        FROM docketwatch.dbo.cases c
        WHERE c.not_found_flag = 1
           OR c.last_updated < DATEADD(day, -30, GETDATE())
           OR (c.last_found IS NULL AND c.created_at < DATEADD(day, -7, GETDATE()))
        ORDER BY c.not_found_count DESC, c.last_updated ASC
    """)
    
    return cursor.fetchall()

def bulk_update_case_status(cursor, case_ids, status, tool_id=None):
    """
    Bulk update status for multiple cases.
    
    Args:
        cursor: Database cursor
        case_ids: List of case IDs to update
        status: New status value
        tool_id: Optional tool ID
        
    Returns:
        int: Number of cases updated
    """
    if not case_ids:
        return 0
    
    # Create parameter placeholders
    placeholders = ','.join('?' * len(case_ids))
    
    # Build query
    query = f"""
        UPDATE docketwatch.dbo.cases
        SET status = ?, last_updated = GETDATE()
        {', fk_tool = ?' if tool_id else ''}
        WHERE id IN ({placeholders})
    """
    
    # Build parameters
    params = [status]
    if tool_id:
        params.append(tool_id)
    params.extend(case_ids)
    
    cursor.execute(query, params)
    updated_count = cursor.rowcount
    cursor.connection.commit()
    
    logging.info(f"Bulk updated {updated_count} cases to status '{status}'")
    return updated_count
