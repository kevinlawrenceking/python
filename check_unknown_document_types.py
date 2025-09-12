#!/usr/bin/env python3
"""
Check for "unknown document type" messages in case events
"""

import pyodbc

def check_unknown_document_types():
    """Check for unknown document type messages"""
    
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        cursor = conn.cursor()
        
        print("🔍 CHECKING FOR 'UNKNOWN DOCUMENT TYPE' MESSAGES")
        print("=" * 55)
        
        # Check for exact phrase
        cursor.execute("""
            SELECT TOP 10 
                id, 
                event_description, 
                event_date,
                fk_cases
            FROM docketwatch.dbo.case_events 
            WHERE event_description LIKE '%unknown document type%'
            ORDER BY id DESC
        """)
        
        exact_matches = cursor.fetchall()
        
        if exact_matches:
            print(f"\n✅ Found {len(exact_matches)} events with 'unknown document type':")
            for i, row in enumerate(exact_matches, 1):
                event_id, desc, event_date, case_id = row
                print(f"\n{i}. Event ID: {event_id}")
                print(f"   Case ID: {case_id}")
                print(f"   Date: {event_date}")
                print(f"   Description: {desc}")
        else:
            print("\n❌ No events found with exact phrase 'unknown document type'")
        
        # Check for partial matches with numbers
        print("\n" + "=" * 55)
        print("🔍 CHECKING FOR 'UNKNOWN' + NUMBERS PATTERN")
        print("=" * 55)
        
        cursor.execute("""
            SELECT TOP 10 
                id, 
                event_description, 
                event_date,
                fk_cases
            FROM docketwatch.dbo.case_events 
            WHERE event_description LIKE '%unknown%'
               AND event_description LIKE '%[0-9]%'
            ORDER BY id DESC
        """)
        
        pattern_matches = cursor.fetchall()
        
        if pattern_matches:
            print(f"\n✅ Found {len(pattern_matches)} events with 'unknown' + numbers:")
            for i, row in enumerate(pattern_matches, 1):
                event_id, desc, event_date, case_id = row
                print(f"\n{i}. Event ID: {event_id}")
                print(f"   Case ID: {case_id}")
                print(f"   Date: {event_date}")
                print(f"   Description: {desc[:100]}...")
        else:
            print("\n❌ No events found with 'unknown' + numbers pattern")
        
        # Check recent events for any suspicious patterns
        print("\n" + "=" * 55)
        print("🔍 CHECKING RECENT EVENTS WITH ERROR-LIKE PATTERNS")
        print("=" * 55)
        
        cursor.execute("""
            SELECT TOP 20 
                id, 
                event_description, 
                event_date,
                fk_cases
            FROM docketwatch.dbo.case_events 
            WHERE (event_description LIKE '%error%'
                OR event_description LIKE '%unknown%'
                OR event_description LIKE '%failed%'
                OR event_description LIKE '%invalid%')
               AND event_date >= DATEADD(day, -7, GETDATE())
            ORDER BY id DESC
        """)
        
        error_matches = cursor.fetchall()
        
        if error_matches:
            print(f"\n✅ Found {len(error_matches)} recent events with error-like patterns:")
            for i, row in enumerate(error_matches, 1):
                event_id, desc, event_date, case_id = row
                print(f"\n{i}. Event ID: {event_id}")
                print(f"   Case ID: {case_id}")
                print(f"   Date: {event_date}")
                print(f"   Description: {desc}")
        else:
            print("\n❌ No recent events found with error-like patterns")
        
        # Check RSS feed entries for the pattern
        print("\n" + "=" * 55)
        print("🔍 CHECKING RSS FEED ENTRIES")
        print("=" * 55)
        
        cursor.execute("""
            SELECT TOP 10 
                id, 
                event_description, 
                pub_date,
                case_number
            FROM docketwatch.dbo.rss_feed_entries 
            WHERE event_description LIKE '%unknown%'
            ORDER BY id DESC
        """)
        
        rss_matches = cursor.fetchall()
        
        if rss_matches:
            print(f"\n✅ Found {len(rss_matches)} RSS entries with 'unknown':")
            for i, row in enumerate(rss_matches, 1):
                entry_id, desc, pub_date, case_number = row
                print(f"\n{i}. RSS Entry ID: {entry_id}")
                print(f"   Case Number: {case_number}")
                print(f"   Date: {pub_date}")
                print(f"   Description: {desc}")
        else:
            print("\n❌ No RSS entries found with 'unknown'")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_unknown_document_types()
