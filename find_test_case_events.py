#!/usr/bin/env python3
"""
Find Case Events for Testing Enhanced PDF Downloader

This script helps you find case events that:
1. Have documents that failed to download (good for testing redisplay fixes)
2. Are recent and likely to still be accessible
3. Have specific error messages related to PDF downloads
"""

import pyodbc
from datetime import datetime, timedelta

def find_test_case_events():
    """Find suitable case events for testing the enhanced PDF downloader"""
    
    print("🔍 FINDING CASE EVENTS FOR TESTING")
    print("=" * 50)
    
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # Find recent case events with failed PDF downloads
        print("\n📋 OPTION 1: Recent events with failed documents")
        print("-" * 50)
        
        cursor.execute("""
            SELECT TOP 10 
                ce.id as case_event_id,
                ce.fk_case,
                ce.event_no,
                ce.court_code,
                c.case_name,
                ce.date_created,
                COUNT(d.id) as doc_count
            FROM case_events ce
            LEFT JOIN cases c ON ce.fk_case = c.id  
            LEFT JOIN documents d ON d.fk_case_event = ce.id
            WHERE ce.date_created >= DATEADD(day, -7, GETDATE())
            AND EXISTS (
                SELECT 1 FROM documents d2 
                WHERE d2.fk_case_event = ce.id 
                AND d2.status IN ('failed', 'pending')
            )
            GROUP BY ce.id, ce.fk_case, ce.event_no, ce.court_code, c.case_name, ce.date_created
            ORDER BY ce.date_created DESC
        """)
        
        recent_events = cursor.fetchall()
        
        for i, (event_id, case_id, event_no, court, case_name, date_created, doc_count) in enumerate(recent_events, 1):
            print(f"\n{i}. Case Event ID: {event_id}")
            print(f"   Case: {case_name}")
            print(f"   Event: {event_no} ({court})")
            print(f"   Date: {date_created}")
            print(f"   Documents: {doc_count}")
            print(f"   Test Command: python test_single_case_event_pdf.py {event_id}")
        
        # Find events specifically with PDF-related errors
        print("\n📋 OPTION 2: Events with PDF-related errors")
        print("-" * 50)
        
        cursor.execute("""
            SELECT TOP 5
                ce.id as case_event_id,
                ce.fk_case,
                ce.event_no, 
                ce.court_code,
                c.case_name,
                d.error_message,
                ce.date_created
            FROM case_events ce
            LEFT JOIN cases c ON ce.fk_case = c.id
            INNER JOIN documents d ON d.fk_case_event = ce.id
            WHERE d.status = 'failed'
            AND (
                d.error_message LIKE '%redisplay%' 
                OR d.error_message LIKE '%PDF%'
                OR d.error_message LIKE '%download%'
                OR d.error_message LIKE '%shown%'
            )
            AND ce.date_created >= DATEADD(day, -30, GETDATE())
            ORDER BY ce.date_created DESC
        """)
        
        error_events = cursor.fetchall()
        
        for i, (event_id, case_id, event_no, court, case_name, error_msg, date_created) in enumerate(error_events, 1):
            print(f"\n{i}. Case Event ID: {event_id}")
            print(f"   Case: {case_name}")
            print(f"   Event: {event_no} ({court})")
            print(f"   Error: {error_msg[:100]}...")
            print(f"   Date: {date_created}")
            print(f"   Test Command: python test_single_case_event_pdf.py {event_id}")
        
        # Find the most recent event (like the one from your log)
        print("\n📋 OPTION 3: Most recent case event (like from your log)")
        print("-" * 55)
        
        cursor.execute("""
            SELECT TOP 1
                ce.id as case_event_id,
                ce.fk_case,
                ce.event_no,
                ce.court_code, 
                c.case_name,
                ce.date_created,
                COUNT(d.id) as doc_count
            FROM case_events ce
            LEFT JOIN cases c ON ce.fk_case = c.id
            LEFT JOIN documents d ON d.fk_case_event = ce.id
            WHERE ce.date_created >= DATEADD(hour, -2, GETDATE())
            GROUP BY ce.id, ce.fk_case, ce.event_no, ce.court_code, c.case_name, ce.date_created
            ORDER BY ce.date_created DESC
        """)
        
        latest_event = cursor.fetchone()
        if latest_event:
            event_id, case_id, event_no, court, case_name, date_created, doc_count = latest_event
            print(f"\nMost Recent Event ID: {event_id}")
            print(f"Case: {case_name}")
            print(f"Event: {event_no} ({court})")
            print(f"Date: {date_created}")
            print(f"Documents: {doc_count}")
            print(f"Test Command: python test_single_case_event_pdf.py {event_id}")
            
            # This might be the Pete v. Cooper case from your log!
            if "Pete" in str(case_name) and "Cooper" in str(case_name):
                print(f"🎯 This looks like the Pete v. Cooper case from your log!")
        
        cursor.close()
        conn.close()
        
        # Provide testing instructions
        print("\n🧪 HOW TO TEST:")
        print("=" * 20)
        print("1. Pick a case event ID from above")
        print("2. Run: python test_single_case_event_pdf.py <case_event_id>")
        print("3. Watch for 'Redisplay error detected' messages")
        print("4. Check if enhanced downloader resolves the issue")
        
        print("\n📝 WHAT TO EXPECT:")
        print("• Enhanced downloader detects PACER errors")
        print("• Creates fresh browser sessions")
        print("• Tries alternative access methods") 
        print("• Successfully downloads previously failed PDFs")
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    find_test_case_events()
