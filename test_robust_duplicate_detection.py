#!/usr/bin/env python3
"""
Test the robust duplicate detection logic.
Tests the new criteria: fk_cases, event_date, event_no (if > 0), first 10 chars of description
"""

import pyodbc
import sys
import os
from datetime import datetime, date

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_robust_duplicate_detection():
    """Test the robust duplicate detection logic"""
    
    try:
        # Connect to database
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.100;"
            "DATABASE=docketwatch;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        
        print("🔍 Testing robust duplicate detection logic...")
        print("📋 Criteria: fk_cases + event_date + event_no (if >0) + first 10 chars of description")
        
        # Test 1: Find recent events to analyze
        print("\n🧪 Test 1: Analyzing recent events for potential duplicates")
        cursor.execute("""
            SELECT TOP 10
                ce.fk_cases, 
                CAST(ce.event_date AS DATE) as event_date,
                ce.event_no, 
                LEFT(ISNULL(ce.event_description, ''), 10) as desc_prefix,
                ce.event_description,
                c.case_name
            FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE ce.created_at >= DATEADD(day, -7, GETDATE())
            ORDER BY ce.created_at DESC
        """)
        
        recent_events = cursor.fetchall()
        if recent_events:
            print(f"📊 Found {len(recent_events)} recent events:")
            for event in recent_events[:3]:  # Show first 3
                fk_case, event_date, event_no, desc_prefix, description, case_name = event
                print(f"   Case {fk_case} ({case_name[:30]}...): Event {event_no}, Date {event_date}, Desc '{desc_prefix}...'")
        
        # Test 2: Check for duplicates using new criteria
        print("\n🧪 Test 2: Checking for duplicates with new criteria")
        
        # For events with event_no > 0
        cursor.execute("""
            SELECT 
                fk_cases,
                CAST(event_date AS DATE) as event_date,
                event_no,
                LEFT(ISNULL(event_description, ''), 10) as desc_prefix,
                COUNT(*) as duplicate_count,
                MIN(id) as first_id,
                MAX(id) as last_id
            FROM docketwatch.dbo.case_events
            WHERE created_at >= DATEADD(day, -3, GETDATE())
              AND event_no > 0
            GROUP BY fk_cases, CAST(event_date AS DATE), event_no, LEFT(ISNULL(event_description, ''), 10)
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """)
        
        duplicates_with_event_no = cursor.fetchall()
        if duplicates_with_event_no:
            print(f"⚠️  Found {len(duplicates_with_event_no)} duplicate sets (with event_no > 0):")
            for dup in duplicates_with_event_no[:3]:
                fk_case, event_date, event_no, desc_prefix, count, first_id, last_id = dup
                print(f"   Case {fk_case}, Date {event_date}, Event {event_no}, Desc '{desc_prefix}...': {count} duplicates (IDs {first_id}-{last_id})")
        else:
            print("✅ No duplicates found with event_no > 0")
        
        # For events with event_no <= 0 (different criteria)
        cursor.execute("""
            SELECT 
                fk_cases,
                CAST(event_date AS DATE) as event_date,
                LEFT(ISNULL(event_description, ''), 10) as desc_prefix,
                COUNT(*) as duplicate_count,
                MIN(event_no) as min_event_no,
                MAX(event_no) as max_event_no
            FROM docketwatch.dbo.case_events
            WHERE created_at >= DATEADD(day, -3, GETDATE())
              AND event_no <= 0
            GROUP BY fk_cases, CAST(event_date AS DATE), LEFT(ISNULL(event_description, ''), 10)
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """)
        
        duplicates_without_event_no = cursor.fetchall()
        if duplicates_without_event_no:
            print(f"⚠️  Found {len(duplicates_without_event_no)} duplicate sets (with event_no <= 0):")
            for dup in duplicates_without_event_no[:3]:
                fk_case, event_date, desc_prefix, count, min_event_no, max_event_no = dup
                print(f"   Case {fk_case}, Date {event_date}, Desc '{desc_prefix}...': {count} duplicates (event_nos {min_event_no}-{max_event_no})")
        else:
            print("✅ No duplicates found with event_no <= 0")
        
        # Test 3: Simulate the new detection logic
        print("\n🧪 Test 3: Simulating new duplicate detection logic")
        if recent_events:
            test_event = recent_events[0]
            fk_case, event_date, event_no, desc_prefix, description, case_name = test_event
            
            print(f"📝 Testing with: Case {fk_case}, Date {event_date}, Event {event_no}")
            print(f"   Description prefix: '{desc_prefix}...'")
            
            # Simulate the new logic
            if event_no > 0:
                cursor.execute("""
                    SELECT id, event_description FROM docketwatch.dbo.case_events
                    WHERE fk_cases = ? 
                      AND CAST(event_date AS DATE) = CAST(? AS DATE)
                      AND event_no = ?
                      AND LEFT(ISNULL(event_description, ''), 10) = ?
                """, (fk_case, event_date, event_no, desc_prefix))
            else:
                cursor.execute("""
                    SELECT id, event_description FROM docketwatch.dbo.case_events
                    WHERE fk_cases = ? 
                      AND CAST(event_date AS DATE) = CAST(? AS DATE)
                      AND LEFT(ISNULL(event_description, ''), 10) = ?
                """, (fk_case, event_date, desc_prefix))
            
            matches = cursor.fetchall()
            print(f"🎯 Found {len(matches)} matching events with new criteria")
            for i, match in enumerate(matches[:3]):
                match_id, match_desc = match
                print(f"   Match {i+1}: ID {match_id}, Desc: '{match_desc[:50]}...'")
        
        # Test 4: Edge cases
        print("\n🧪 Test 4: Testing edge cases")
        
        # Empty descriptions
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE created_at >= DATEADD(day, -7, GETDATE())
              AND (event_description IS NULL OR event_description = '')
        """)
        empty_desc_count = cursor.fetchone()[0]
        print(f"📊 Events with empty descriptions: {empty_desc_count}")
        
        # Very short descriptions (< 10 chars)
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.case_events
            WHERE created_at >= DATEADD(day, -7, GETDATE())
              AND LEN(ISNULL(event_description, '')) < 10
              AND LEN(ISNULL(event_description, '')) > 0
        """)
        short_desc_count = cursor.fetchone()[0]
        print(f"📊 Events with short descriptions (<10 chars): {short_desc_count}")
        
        conn.close()
        print("\n🎉 Robust duplicate detection tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    test_robust_duplicate_detection()
