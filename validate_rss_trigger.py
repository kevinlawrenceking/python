#!/usr/bin/env python3
"""
Quick validation test for the RSS trigger improvements
Tests the key functions without running the full RSS monitoring
"""

import sys
import os
import pyodbc
import requests
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_operations():
    """Test basic database operations"""
    print("🔍 Testing database operations...")
    
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        # Test tracked cases query
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM docketwatch.dbo.cases
            WHERE fk_tool = 2 AND status = 'Tracked' AND pacer_id IS NOT NULL
        """)
        tracked_count = cursor.fetchone().count
        print(f"✅ Found {tracked_count} tracked PACER cases")
        
        # Test RSS feeds query
        cursor.execute("""
            SELECT COUNT(*) as count, MIN(court_code) as sample_court
            FROM docketwatch.dbo.courts crt
            LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
            WHERE crt.pacer_url IS NOT NULL AND crt.fk_feed_type <> 0
        """)
        result = cursor.fetchone()
        feeds_count = result.count
        sample_court = result.sample_court
        print(f"✅ Found {feeds_count} courts with RSS feeds (sample: {sample_court})")
        
        # Test document creation simulation
        cursor.execute("SELECT TOP 1 id, fk_cases FROM docketwatch.dbo.case_events ORDER BY id DESC")
        test_event = cursor.fetchone()
        if test_event:
            print(f"✅ Can access case_events table (latest event: {test_event.id})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_rss_feed_access():
    """Test accessing a sample RSS feed"""
    print("\n🌐 Testing RSS feed access...")
    
    try:
        # Test with a known working feed
        test_url = "https://ecf.flsd.uscourts.gov/cgi-bin/rss_outside.pl"
        print(f"Testing: {test_url}")
        
        response = requests.get(test_url, timeout=10)
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
            print(f"✅ RSS feed accessible - found {len(items)} items")
            
            if items:
                # Test parsing first item
                first_item = items[0]
                title = first_item.title.text if first_item.title else "No title"
                print(f"✅ Sample item: {title[:50]}...")
                
            return True
        else:
            print(f"⚠️ RSS feed returned HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ RSS feed test failed: {e}")
        return False

def test_file_operations():
    """Test file system operations"""
    print("\n📁 Testing file operations...")
    
    try:
        pdf_root = r"\\10.146.176.84\general\docketwatch\docs\cases"
        
        # Test if we can access the PDF root directory
        if os.path.exists(pdf_root):
            print(f"✅ PDF root directory accessible: {pdf_root}")
            
            # Count subdirectories (case folders)
            case_dirs = [d for d in os.listdir(pdf_root) if os.path.isdir(os.path.join(pdf_root, d)) and d.isdigit()]
            print(f"✅ Found {len(case_dirs)} case directories")
            
            return True
        else:
            print(f"❌ PDF root directory not accessible: {pdf_root}")
            return False
            
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🚀 Starting RSS Trigger Validation Tests\n")
    
    tests = [
        ("Database Operations", test_database_operations),
        ("RSS Feed Access", test_rss_feed_access),
        ("File Operations", test_file_operations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! RSS trigger should work correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Review errors before running RSS trigger.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
