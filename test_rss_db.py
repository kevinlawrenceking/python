#!/usr/bin/env python3
"""Test RSS trigger database operations"""

import sys
import os
import pyodbc
from datetime import datetime

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_rss_db_operations():
    try:
        # Test database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("✓ Database connection successful")

        # Test case_events table operations
        print("\nTesting case_events operations...")
        
        # Check if we can read from case_events
        cursor.execute("SELECT TOP 1 id, fk_cases, event_no FROM docketwatch.dbo.case_events ORDER BY id DESC")
        event = cursor.fetchone()
        if event:
            print(f"✓ Can read case_events: event_id={event.id}, fk_case={event.fk_cases}, event_no={event.event_no}")
        else:
            print("⚠ No case_events found")

        # Test documents table operations
        print("\nTesting documents operations...")
        
        # Check if we can read from documents
        cursor.execute("SELECT TOP 1 doc_uid, fk_case, pdf_url, rel_path FROM docketwatch.dbo.documents ORDER BY doc_uid DESC")
        doc = cursor.fetchone()
        if doc:
            print(f"✓ Can read documents: doc_uid={doc.doc_uid}, fk_case={doc.fk_case}")
            print(f"  pdf_url={doc.pdf_url[:50] if doc.pdf_url else 'None'}...")
            print(f"  rel_path={doc.rel_path}")
        else:
            print("⚠ No documents found")

        # Test tracked cases query
        print("\nTesting tracked cases query...")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM docketwatch.dbo.cases
            WHERE fk_tool = 2 AND status = 'Tracked' AND pacer_id IS NOT NULL
        """)
        tracked_count = cursor.fetchone().count
        print(f"✓ Found {tracked_count} tracked PACER cases")

        # Test courts/RSS feeds query
        print("\nTesting courts/RSS feeds query...")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM docketwatch.dbo.courts crt
            LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
            WHERE crt.pacer_url IS NOT NULL AND crt.fk_feed_type <> 0
        """)
        courts_count = cursor.fetchone().count
        print(f"✓ Found {courts_count} courts with RSS feeds configured")

        conn.close()
        print("\n✅ All database operations test successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rss_db_operations()
    sys.exit(0 if success else 1)
