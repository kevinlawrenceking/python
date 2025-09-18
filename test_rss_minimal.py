#!/usr/bin/env python3
"""
Minimal RSS Trigger Test - bypasses task_run lookup for debugging
"""
import pyodbc
import requests
from bs4 import BeautifulSoup

print("=== Minimal RSS Trigger Test ===")

try:
    # Database connection
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    print("✓ Database connected")
    
    # Use a dummy fk_task_run for testing
    fk_task_run = 1
    
    # Test: Get tracked cases
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM docketwatch.dbo.cases
        WHERE fk_tool = 2 AND status = 'Tracked' AND pacer_id IS NOT NULL
    """)
    tracked_count = cursor.fetchone()[0]
    print(f"✓ Found {tracked_count} tracked PACER cases")
    
    # Test: Get courts with RSS feeds
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM docketwatch.dbo.courts crt
        LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
        WHERE crt.pacer_url IS NOT NULL AND crt.fk_feed_type <> 0
    """)
    court_count = cursor.fetchone()[0]
    print(f"✓ Found {court_count} courts with RSS feeds")
    
    # Test: Basic RSS feed access (try one court)
    cursor.execute("""
        SELECT TOP 1 crt.court_code, crt.pacer_url, ft.url_suffix
        FROM docketwatch.dbo.courts crt
        LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
        WHERE crt.pacer_url IS NOT NULL AND crt.fk_feed_type <> 0
    """)
    court_row = cursor.fetchone()
    
    if court_row:
        court_code, base_url, url_suffix = court_row
        rss_url = base_url.rstrip("/") + (url_suffix or "/cgi-bin/rss_outside.pl")
        print(f"✓ Testing RSS URL: {rss_url}")
        
        try:
            response = requests.get(rss_url, timeout=10)
            print(f"✓ RSS Response: HTTP {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
                print(f"✓ Found {len(items)} RSS items")
            else:
                print(f"✗ HTTP error: {response.status_code}")
                
        except Exception as e:
            print(f"✗ RSS request failed: {e}")
    
    cursor.close()
    conn.close()
    print("✓ Test completed successfully")
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()