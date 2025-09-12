#!/usr/bin/env python3
"""
Simple Case Event Finder for Testing
Find recent case events to test the enhanced PDF downloader.
"""

import pyodbc

def find_recent_case_events():
    """Find recent case events for testing"""
    
    print("🔍 FINDING RECENT CASE EVENTS FOR TESTING")
    print("=" * 50)
    
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # First, let's see what tables and columns we have
        print("\n📋 Looking for recent case events...")
        
        # Try a simple query to find recent case events
        cursor.execute("""
            SELECT TOP 10 id, court_code, event_no
            FROM case_events
            ORDER BY id DESC
        """)
        
        events = cursor.fetchall()
        
        if events:
            print(f"\nFound {len(events)} recent case events:")
            print("-" * 40)
            
            for i, (event_id, court_code, event_no) in enumerate(events, 1):
                print(f"{i}. Event ID: {event_id}")
                print(f"   Court: {court_code}")
                print(f"   Event No: {event_no}")
                
                # Check if this event has documents
                cursor.execute("SELECT COUNT(*) FROM documents WHERE fk_case_event = ?", (event_id,))
                doc_count = cursor.fetchone()[0]
                print(f"   Documents: {doc_count}")
                
                print(f"   Test Command: python test_single_case_event_pdf.py {event_id}")
                print("-" * 40)
        else:
            print("No case events found")
        
        # Based on your log, let's look for the Pete v. Cooper case specifically
        print("\n🎯 LOOKING FOR PETE V. COOPER CASE (from your log):")
        print("-" * 50)
        
        cursor.execute("""
            SELECT TOP 5 ce.id, ce.court_code, ce.event_no, c.case_name
            FROM case_events ce
            LEFT JOIN cases c ON ce.case_id = c.id
            WHERE c.case_name LIKE '%Pete%Cooper%' OR c.case_name LIKE '%Cooper%Pete%'
            ORDER BY ce.id DESC
        """)
        
        pete_cases = cursor.fetchall()
        if pete_cases:
            for event_id, court_code, event_no, case_name in pete_cases:
                print(f"Found: {case_name}")
                print(f"Event ID: {event_id} (Event {event_no}, {court_code})")
                print(f"Test Command: python test_single_case_event_pdf.py {event_id}")
        else:
            # Try different column name
            cursor.execute("""
                SELECT TOP 5 ce.id, ce.court_code, ce.event_no, c.case_name
                FROM case_events ce
                LEFT JOIN cases c ON ce.fk_case = c.id
                WHERE c.case_name LIKE '%Pete%Cooper%' OR c.case_name LIKE '%Cooper%Pete%'
                ORDER BY ce.id DESC
            """)
            
            pete_cases = cursor.fetchall()
            if pete_cases:
                for event_id, court_code, event_no, case_name in pete_cases:
                    print(f"Found: {case_name}")
                    print(f"Event ID: {event_id} (Event {event_no}, {court_code})")
                    print(f"Test Command: python test_single_case_event_pdf.py {event_id}")
            else:
                print("Pete v. Cooper case not found in recent events")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")
        
        # Provide manual testing option
        print("\n💡 MANUAL TESTING OPTION:")
        print("From your log, the recent case event ID was likely:")
        print("Event No: 138 for Pete v. Cooper case")
        print("\nYou can try:")
        print("1. Look in your database for the most recent case_event")
        print("2. Find the case_event ID for Pete v. Cooper, Event 138")
        print("3. Run: python test_single_case_event_pdf.py <case_event_id>")

if __name__ == "__main__":
    find_recent_case_events()
