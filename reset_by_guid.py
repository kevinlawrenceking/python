#!/usr/bin/env python3
"""
Reset specific RSS GUID for re-testing
Use this when you know the exact RSS entry you want to retest
"""

import pyodbc

def reset_by_guid(guid):
    """Reset a specific RSS entry by its GUID"""
    
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    try:
        # Get the RSS entry details
        cursor.execute("""
            SELECT rfe.pacer_id, rfe.event_no, rfe.case_name, c.id as fk_case
            FROM docketwatch.dbo.rss_feed_entries rfe
            LEFT JOIN docketwatch.dbo.cases c ON c.pacer_id = rfe.pacer_id
            WHERE rfe.guid = ?
        """, (guid,))
        
        entry = cursor.fetchone()
        if not entry:
            print(f"❌ RSS entry with GUID {guid} not found")
            return False
            
        print(f"Found RSS entry: {entry.case_name}, event_no={entry.event_no}")
        
        # Find related case_event
        if entry.fk_case and entry.event_no:
            cursor.execute("""
                SELECT id FROM docketwatch.dbo.case_events 
                WHERE fk_cases = ? AND event_no = ?
            """, (entry.fk_case, entry.event_no))
            event = cursor.fetchone()
            
            if event:
                # Delete related documents
                cursor.execute("""
                    DELETE FROM docketwatch.dbo.documents 
                    WHERE fk_case_event = ?
                """, (event.id,))
                docs_deleted = cursor.rowcount
                
                # Delete the case event
                cursor.execute("""
                    DELETE FROM docketwatch.dbo.case_events 
                    WHERE id = ?
                """, (event.id,))
                events_deleted = cursor.rowcount
                
                print(f"Deleted {docs_deleted} documents and {events_deleted} case events")
        
        # Delete the RSS entry
        cursor.execute("DELETE FROM docketwatch.dbo.rss_feed_entries WHERE guid = ?", (guid,))
        rss_deleted = cursor.rowcount
        
        conn.commit()
        print(f"✅ Successfully reset RSS entry {guid}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        guid = sys.argv[1]
        reset_by_guid(guid)
    else:
        print("Usage: python reset_by_guid.py <RSS_GUID>")
        print("Example: python reset_by_guid.py 'https://ecf.nysd.uscourts.gov/cgi-bin/rss_outside.pl?12345-67890'")
