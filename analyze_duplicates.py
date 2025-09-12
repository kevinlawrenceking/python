#!/usr/bin/env python3
"""
Script to analyze duplicate case events issue
"""

import pyodbc
from datetime import datetime, timedelta

def main():
    try:
        # Get database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("✅ Database connected")
        
        # Look for potential duplicates in case_events from today
        print("\n=== Analyzing potential duplicate case events (today) ===")
        cursor.execute("""
            SELECT 
                fk_cases,
                event_no,
                event_description,
                event_date,
                COUNT(*) as duplicate_count
            FROM docketwatch.dbo.case_events 
            WHERE CONVERT(date, created_at) = CONVERT(date, GETDATE())
            GROUP BY fk_cases, event_no, event_description, event_date
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"⚠️  Found {len(duplicates)} sets of duplicate events:")
            for row in duplicates:
                fk_case, event_no, desc, event_date, count = row
                print(f"   Case {fk_case}, Event {event_no}: {count} duplicates")
                print(f"   Description: {desc}")
                print(f"   Event Date: {event_date}")
                print()
        else:
            print("✅ No exact duplicates found (same case, event_no, description, date)")
        
        # Look for same case/event_no but different descriptions (potential updates)
        print("\n=== Analyzing same event_no with different descriptions ===")
        cursor.execute("""
            SELECT 
                ce1.fk_cases,
                ce1.event_no,
                ce1.event_description as desc1,
                ce2.event_description as desc2,
                ce1.created_at as created1,
                ce2.created_at as created2,
                c.case_name
            FROM docketwatch.dbo.case_events ce1
            INNER JOIN docketwatch.dbo.case_events ce2 
                ON ce1.fk_cases = ce2.fk_cases 
                AND ce1.event_no = ce2.event_no 
                AND ce1.id != ce2.id
                AND ce1.event_description != ce2.event_description
            INNER JOIN docketwatch.dbo.cases c ON ce1.fk_cases = c.id
            WHERE CONVERT(date, ce1.created_at) = CONVERT(date, GETDATE())
               OR CONVERT(date, ce2.created_at) = CONVERT(date, GETDATE())
            ORDER BY ce1.fk_cases, ce1.event_no, ce1.created_at
        """)
        
        desc_changes = cursor.fetchall()
        if desc_changes:
            print(f"⚠️  Found {len(desc_changes)} events with description changes:")
            for row in desc_changes:
                fk_case, event_no, desc1, desc2, created1, created2, case_name = row
                print(f"   Case: {case_name} (ID: {fk_case})")
                print(f"   Event No: {event_no}")
                print(f"   Original: {desc1} (created: {created1})")
                print(f"   Updated:  {desc2} (created: {created2})")
                print()
        else:
            print("✅ No events found with description changes")
            
        # Look for events created very close together (potential race condition)
        print("\n=== Analyzing events created within minutes of each other ===")
        cursor.execute("""
            SELECT 
                ce1.fk_cases,
                ce1.event_no,
                ce1.event_description,
                ce1.created_at,
                ce2.created_at,
                DATEDIFF(SECOND, ce1.created_at, ce2.created_at) as seconds_apart,
                c.case_name
            FROM docketwatch.dbo.case_events ce1
            INNER JOIN docketwatch.dbo.case_events ce2 
                ON ce1.fk_cases = ce2.fk_cases 
                AND ce1.event_no = ce2.event_no 
                AND ce1.id != ce2.id
            INNER JOIN docketwatch.dbo.cases c ON ce1.fk_cases = c.id
            WHERE CONVERT(date, ce1.created_at) = CONVERT(date, GETDATE())
               OR CONVERT(date, ce2.created_at) = CONVERT(date, GETDATE())
            ORDER BY seconds_apart ASC
        """)
        
        timing_issues = cursor.fetchall()
        if timing_issues:
            print(f"⚠️  Found {len(timing_issues)} events created close together:")
            for row in timing_issues:
                fk_case, event_no, desc, created1, created2, seconds, case_name = row
                print(f"   Case: {case_name} (ID: {fk_case})")
                print(f"   Event No: {event_no}")
                print(f"   Description: {desc}")
                print(f"   Times: {created1} and {created2} ({seconds} seconds apart)")
                print()
        else:
            print("✅ No timing issues found")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
