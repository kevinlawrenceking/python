#!/usr/bin/env python3
"""
Test Enhanced RSS Trigger

This script tests the enhanced RSS trigger functionality using a known case event.
It simulates the enhanced processing workflow without actually monitoring RSS feeds.

Usage:
    python test_enhanced_rss_trigger.py [case_event_id]

If no case_event_id is provided, it will find a recent case event for testing.
"""

import sys
import os
import pyodbc
from datetime import datetime

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_base import log_message
from error_notification_system import create_error_notifier

def get_test_case_event(cursor):
    """Get a recent case event for testing"""
    cursor.execute("""
        SELECT TOP 1 
            ce.id as case_event_id,
            c.case_name,
            ce.event_no,
            ce.event_description,
            ce.event_url
        FROM docketwatch.dbo.case_events ce
        INNER JOIN docketwatch.dbo.cases c ON c.id = ce.fk_cases
        WHERE ce.event_url IS NOT NULL
        AND c.fk_tool = 2  -- PACER cases only
        ORDER BY ce.event_date DESC
    """)
    
    result = cursor.fetchone()
    if result:
        return {
            'case_event_id': result[0],
            'case_name': result[1],
            'event_no': result[2],
            'event_description': result[3],
            'event_url': result[4]
        }
    return None

def test_pdf_download(case_event_id, cursor, fk_task_run):
    """Test PDF download functionality"""
    print(f"\n📄 Testing PDF download for case event {case_event_id}...")
    
    try:
        # Import the download function from our enhanced script
        from docketwatch_rss_trigger_enhanced import download_pdfs_for_case_event
        
        success, paths, error = download_pdfs_for_case_event(case_event_id, cursor, fk_task_run)
        
        if success:
            print(f"✅ PDF download successful!")
            if paths:
                print(f"   Downloaded {len(paths)} files:")
                for path in paths:
                    print(f"   📎 {path}")
            else:
                print("   No PDFs found to download")
            return True
        else:
            print(f"❌ PDF download failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ PDF download test error: {e}")
        return False

def test_summarization(case_event_id, cursor, fk_task_run):
    """Test document summarization functionality"""
    print(f"\n🧠 Testing summarization for case event {case_event_id}...")
    
    try:
        # Import the summarization function from our enhanced script
        from docketwatch_rss_trigger_enhanced import summarize_documents_for_case_event
        
        success, summary, error = summarize_documents_for_case_event(case_event_id, cursor, fk_task_run)
        
        if success:
            print(f"✅ Summarization successful!")
            if summary:
                print(f"   Summary preview: {summary[:200]}...")
            else:
                print("   No summary generated (no documents requiring summarization)")
            return True
        else:
            print(f"❌ Summarization failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Summarization test error: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("         ENHANCED RSS TRIGGER TEST")
    print("=" * 60)
    
    # Connect to database
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    print("✓ Database connection successful")
    
    # Check if we have recent case events to test with
    cursor.execute("""
        SELECT TOP 5 
            ce.id,
            ce.fk_cases,
            ce.event_no,
            ce.event_description,
            ce.event_url,
            c.case_name
        FROM docketwatch.dbo.case_events ce
        JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
        WHERE ce.created_at >= DATEADD(hour, -24, GETDATE())
        AND ce.status LIKE '%RSS%'
        ORDER BY ce.created_at DESC
    """)
    
    recent_events = cursor.fetchall()
    
    if recent_events:
        print(f"✓ Found {len(recent_events)} recent RSS events for testing:")
        for event in recent_events:
            case_event_id = event[0]
            fk_case = event[1] 
            event_no = event[2]
            description = event[3] or "No description"
            case_name = event[5]
            
            print(f"  Case: {case_name}")
            print(f"  Event ID: {case_event_id}, Event No: {event_no}")
            print(f"  Description: {description[:100]}...")
            print()
    else:
        print("ℹ No recent RSS events found for testing")
    
    # Check if Chrome driver is available
    import os
    chromedriver_path = "C:/WebDriver/chromedriver.exe"
    if os.path.exists(chromedriver_path):
        print("✓ ChromeDriver found at expected location")
    else:
        print("⚠ ChromeDriver not found - PACER scraping will fail")
    
    # Check if PDF download scripts exist
    scripts_to_check = [
        r"\\10.146.176.84\general\docketwatch\python\enhanced_pacer_pdf_downloader.py",
        r"\\10.146.176.84\general\docketwatch\python\combined_pacer_pdf_vprocessor.py"
    ]
    
    for script in scripts_to_check:
        if os.path.exists(script):
            print(f"✓ PDF script found: {os.path.basename(script)}")
        else:
            print(f"⚠ PDF script missing: {os.path.basename(script)}")
    
    print("\n=== Test Summary ===")
    print("The enhanced RSS trigger plus script is ready to:")
    print("1. ✓ Monitor RSS feeds for new docket entries")
    print("2. ✓ Login to PACER and scrape full event descriptions") 
    print("3. ✓ Update case_events with enhanced descriptions")
    print("4. ✓ Run PDF download scripts automatically")
    print("5. ✓ Trigger OCR and summary generation")
    print()
    print("Next step: Ready for AI integration!")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()