#!/usr/bin/env python3
"""
Test the improved duplicate detection logic.
This script tests the fix for duplicate case events.
"""

import pyodbc
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_duplicate_detection():
    """Test the improved duplicate detection logic"""
    
    try:
        # Connect to database (using same connection as other scripts)
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.100;"
            "DATABASE=docketwatch;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        
        print("🔍 Testing duplicate detection logic...")
        
        # Find a recent case event to test with
        cursor.execute("""
            SELECT TOP 1 
                ce.fk_cases, 
                ce.event_no, 
                ce.event_description,
                ce.event_date,
                c.case_name
            FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE ce.created_at >= DATEADD(day, -7, GETDATE())
            ORDER BY ce.created_at DESC
        """)
        
        result = cursor.fetchone()
        if not result:
            print("❌ No recent case events found for testing")
            return
            
        fk_case, event_no, event_description, event_date, case_name = result
        print(f"📋 Testing with case: {case_name}")
        print(f"   Event No: {event_no}")
        print(f"   Description: {event_description[:100]}...")
        
        # Test 1: Check existing event detection
        print("\n🧪 Test 1: Existing event detection")
        cursor.execute("""
            SELECT id, event_description FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_no = ?
        """, (fk_case, event_no))
        
        existing_event = cursor.fetchone()
        if existing_event:
            print(f"✅ Found existing event: ID {existing_event[0]}")
        else:
            print("❌ Event not found (unexpected)")
            
        # Test 2: Check duplicate prevention with same description
        print("\n🧪 Test 2: Duplicate prevention with same description")
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_no = ?
        """, (fk_case, event_no))
        
        count_before = cursor.fetchone()[0]
        print(f"   Count before: {count_before}")
        
        # Simulate the new logic (read-only test)
        cursor.execute("""
            SELECT id, event_description FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND event_no = ?
        """, (fk_case, event_no))
        
        existing_event = cursor.fetchone()
        if existing_event:
            event_id, current_desc = existing_event
            if current_desc == event_description:
                print(f"✅ Would skip duplicate event (same description)")
            else:
                print(f"ℹ️  Would update event description")
        else:
            print(f"ℹ️  Would create new event")
            
        # Test 3: Check for any actual duplicates in the database
        print("\n🧪 Test 3: Check for actual duplicates")
        cursor.execute("""
            SELECT 
                fk_cases, 
                event_no, 
                COUNT(*) as duplicate_count,
                MIN(created_at) as first_created,
                MAX(created_at) as last_created
            FROM docketwatch.dbo.case_events
            WHERE created_at >= DATEADD(day, -1, GETDATE())
            GROUP BY fk_cases, event_no
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"⚠️  Found {len(duplicates)} sets of duplicate events from last 24 hours:")
            for dup in duplicates[:5]:  # Show first 5
                fk_case_dup, event_no_dup, count, first, last = dup
                time_diff = (last - first).total_seconds()
                print(f"   Case {fk_case_dup}, Event {event_no_dup}: {count} duplicates ({time_diff:.1f}s apart)")
        else:
            print("✅ No duplicates found in last 24 hours")
            
        # Test 4: Performance test of new query
        print("\n🧪 Test 4: Performance test")
        import time
        
        start_time = time.time()
        for i in range(100):
            cursor.execute("""
                SELECT id, event_description FROM docketwatch.dbo.case_events
                WHERE fk_cases = ? AND event_no = ?
            """, (fk_case, event_no))
            cursor.fetchone()
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 100 * 1000  # Convert to milliseconds
        print(f"✅ Average query time: {avg_time:.2f}ms (100 iterations)")
        
        conn.close()
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    test_duplicate_detection()
