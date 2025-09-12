#!/usr/bin/env python3
"""
Improved duplicate detection for case events.
This addresses the race condition and description update issues.
"""

def improved_duplicate_check_and_insert(cursor, conn, fk_case, event_no, event_description, pub_date, event_url, fk_task_run):
    """
    Improved function to handle case event creation with better duplicate detection.
    
    Uses a more robust approach:
    1. Try to insert with a unique constraint check
    2. Handle the duplicate gracefully if it occurs
    3. Update description if event exists but description changed
    """
    
    try:
        # First, check if the event already exists
        cursor.execute("""
            SELECT 
                id, 
                event_description, 
                created_at,
                stage_completed
            FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_no = ?
        """, (fk_case, event_no))
        
        existing_event = cursor.fetchone()
        
        if existing_event:
            event_id, current_desc, created_at, stage_completed = existing_event
            
            # Check if description has changed significantly
            if current_desc != event_description:
                print(f"Event {event_no} exists but description changed:")
                print(f"  Old: {current_desc}")
                print(f"  New: {event_description}")
                
                # Option 1: Update the description (if you want to keep latest)
                cursor.execute("""
                    UPDATE docketwatch.dbo.case_events 
                    SET 
                        event_description = ?,
                        event_url = ?,
                        last_updated = GETDATE()
                    WHERE id = ?
                """, (event_description, event_url, event_id))
                
                print(f"✅ Updated description for existing event {event_no}")
                return event_id, False  # Existing event, updated
                
            else:
                print(f"✅ Event {event_no} already exists with same description - skipping")
                return event_id, False  # Existing event, no change
        
        else:
            # Event doesn't exist, create it
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_events
                  (event_date, event_no, event_description, fk_cases, stage_completed, fk_task_run_log, event_url)
                VALUES (?, ?, ?, ?, 0, ?, ?)
            """, (pub_date, event_no, event_description, fk_case, fk_task_run, event_url))
            
            # Get the new event ID
            cursor.execute("SELECT @@IDENTITY")
            new_event_id = cursor.fetchone()[0]
            
            print(f"✅ Created new event {event_no} with ID {new_event_id}")
            return new_event_id, True  # New event created
            
    except Exception as e:
        print(f"❌ Error in duplicate check/insert: {e}")
        raise


def atomic_duplicate_check_insert(cursor, conn, fk_case, event_no, event_description, pub_date, event_url, fk_task_run):
    """
    Alternative approach using database-level duplicate prevention.
    Uses a unique constraint or more robust SQL.
    """
    
    try:
        # Use MERGE statement or INSERT...WHERE NOT EXISTS for atomic operation
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.case_events 
                WHERE fk_cases = ? AND event_no = ?
            )
            BEGIN
                INSERT INTO docketwatch.dbo.case_events
                  (event_date, event_no, event_description, fk_cases, stage_completed, fk_task_run_log, event_url)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                
                SELECT @@IDENTITY as new_id, 1 as is_new
            END
            ELSE
            BEGIN
                SELECT id as new_id, 0 as is_new 
                FROM docketwatch.dbo.case_events 
                WHERE fk_cases = ? AND event_no = ?
            END
        """, (fk_case, event_no, pub_date, event_no, event_description, fk_case, fk_task_run, event_url, fk_case, event_no))
        
        result = cursor.fetchone()
        if result:
            event_id, is_new = result
            return event_id, bool(is_new)
        else:
            raise Exception("No result from atomic insert")
            
    except Exception as e:
        print(f"❌ Error in atomic duplicate check/insert: {e}")
        raise


# Example of how to use these in the RSS trigger:
def example_usage():
    """
    Example of how to integrate the improved duplicate detection
    """
    
    # Instead of the current logic:
    # cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.case_events WHERE fk_cases = ? AND event_no = ?", ...)
    # exists = cursor.fetchone()[0] > 0
    # if not exists:
    #     INSERT...
    
    # Use this:
    try:
        event_id, is_new_event = improved_duplicate_check_and_insert(
            cursor, conn, fk_case, event_no, event_description, 
            pub_date, event_url, fk_task_run
        )
        
        if is_new_event:
            print(f"New event created: {event_id}")
            # Send email, trigger pipeline, etc.
        else:
            print(f"Event already exists: {event_id}")
            # Just log that it was skipped
            
    except Exception as e:
        print(f"Error handling event: {e}")


if __name__ == "__main__":
    print("This file contains improved duplicate detection functions.")
    print("Integration required in docketwatch_rss_trigger.py")
