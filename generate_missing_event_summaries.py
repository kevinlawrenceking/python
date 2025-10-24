"""
Generate Event Summaries for Case Events

This script generates event-level summaries for case_events that have document summaries
but are missing the event-level summary in case_events.summarize.

Usage:
    python generate_missing_event_summaries.py [--event-id <GUID>] [--limit <N>]

Options:
    --event-id <GUID>  Process a specific event (optional)
    --limit <N>        Maximum number of events to process (default: 10)
    --all              Process all events missing summaries (ignores limit)
"""

import sys
import os
import argparse
import pyodbc
import traceback
from datetime import datetime

# Add the script directory to path to import summarize_document_event
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from summarize_document_event import generate_event_summary, _simple_log


def get_events_needing_summaries(cursor, event_id=None, limit=10):
    """
    Get case_events that have at least one document with a summary
    but are missing the event-level summary.
    """
    if event_id:
        cursor.execute("""
            SELECT DISTINCT
                e.id,
                e.event_description,
                e.event_date,
                c.case_name,
                c.case_number,
                COUNT(d.doc_uid) as doc_count
            FROM docketwatch.dbo.case_events e
            JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            JOIN docketwatch.dbo.documents d ON d.fk_case_event = e.id
            WHERE e.id = CAST(? AS uniqueidentifier)
              AND d.event_summary IS NOT NULL
            GROUP BY e.id, e.event_description, e.event_date, c.case_name, c.case_number
        """, (event_id,))
    else:
        cursor.execute(f"""
            SELECT TOP {limit}
                e.id,
                e.event_description,
                e.event_date,
                c.case_name,
                c.case_number,
                COUNT(d.doc_uid) as doc_count
            FROM docketwatch.dbo.case_events e
            JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            JOIN docketwatch.dbo.documents d ON d.fk_case_event = e.id
            WHERE (e.summarize IS NULL OR e.summarize = '')
              AND d.event_summary IS NOT NULL
              AND c.status = 'Tracked'
            GROUP BY e.id, e.event_description, e.event_date, c.case_name, c.case_number
            HAVING COUNT(d.doc_uid) > 0
            ORDER BY e.event_date DESC
        """)
    
    return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser(description='Generate missing event summaries')
    parser.add_argument('--event-id', type=str, help='Process a specific event GUID')
    parser.add_argument('--limit', type=int, default=10, help='Maximum events to process')
    parser.add_argument('--all', action='store_true', help='Process all missing event summaries')
    
    args = parser.parse_args()
    
    # Connect to database
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("✓ Connected to database")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return 1
    
    try:
        # Get events needing summaries
        if args.all and not args.event_id:
            limit = 999999  # Large number
        else:
            limit = args.limit
        
        events = get_events_needing_summaries(cursor, args.event_id, limit)
        
        if not events:
            print("No events found needing summaries.")
            return 0
        
        print(f"\nFound {len(events)} event(s) needing summaries:\n")
        
        # Process each event
        success_count = 0
        fail_count = 0
        
        for event in events:
            event_id = str(event.id)
            case_name = event.case_name or "Unknown Case"
            case_number = event.case_number or "Unknown"
            event_desc = event.event_description or "Unknown Event"
            # Handle event_date - might be string or datetime
            if event.event_date:
                if hasattr(event.event_date, 'strftime'):
                    event_date = event.event_date.strftime('%Y-%m-%d')
                else:
                    event_date = str(event.event_date)
            else:
                event_date = "Unknown"
            doc_count = event.doc_count
            
            print(f"Processing event {event_id}:")
            print(f"  Case: {case_name} ({case_number})")
            print(f"  Event: {event_desc}")
            print(f"  Date: {event_date}")
            print(f"  Documents: {doc_count}")
            
            try:
                summary = generate_event_summary(cursor, event_id)
                if summary:
                    conn.commit()
                    print(f"  ✓ Generated: {summary[:100]}...")
                    success_count += 1
                else:
                    print(f"  ✗ Failed to generate summary (returned None)")
                    fail_count += 1
            except Exception as e:
                print(f"  ✗ Error: {e}")
                tb = traceback.format_exc()
                print(f"  Traceback: {tb}")
                fail_count += 1
            
            print()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"SUMMARY:")
        print(f"  Total events processed: {len(events)}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {fail_count}")
        print(f"{'='*60}\n")
        
        return 0 if fail_count == 0 else 1
        
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        tb = traceback.format_exc()
        print(tb)
        return 1
    finally:
        cursor.close()
        conn.close()
        print("✓ Database connection closed")


if __name__ == "__main__":
    sys.exit(main())
