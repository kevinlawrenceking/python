#!/usr/bin/env python3
"""
Minimal test script to debug MAP case summarizer issues
"""

import sys
import pyodbc
from scraper_base import get_db_cursor, get_task_context_by_tool_id

def test_db_connection():
    """Test database connection"""
    try:
        print("Testing database connection...")
        conn, cursor = get_db_cursor()
        print("✓ Database connection successful")
        
        print("Testing task context...")
        context = get_task_context_by_tool_id(cursor, 12)
        if context:
            print(f"✓ Task context found: {context}")
        else:
            print("⚠ No task context found, will use fallback method")
        
        print("Testing direct credentials query...")
        cursor.execute("SELECT [login_url], [username], [pass] FROM [docketwatch].[dbo].[tools] WHERE id = 12")
        login_row = cursor.fetchone()
        if login_row:
            login_url, username, password = login_row
            print(f"✓ Credentials found: {login_url[:30]}..., {username}, {'*' * len(password)}")
        else:
            print("✗ No credentials found")
            
        print("Testing Gemini key...")
        cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
        gemini_row = cursor.fetchone()
        if gemini_row and gemini_row[0]:
            print("✓ Gemini API key found")
        else:
            print("✗ No Gemini API key found")
            
        print("Testing case query...")
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.cases 
            WHERE fk_tool = 12 
              AND status = 'Tracked' 
              AND map_id IS NOT NULL 
              AND (summarize IS NULL OR LEN(LTRIM(RTRIM(ISNULL(summarize, '')))) = 0)
        """)
        count = cursor.fetchone()[0]
        print(f"✓ Found {count} cases that need summarization")
        
        cursor.close()
        conn.close()
        print("✓ Database connection closed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def test_chromedriver():
    """Test ChromeDriver without actually launching"""
    try:
        print("Testing ChromeDriver availability...")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
        options = Options()
        options.add_argument("--version")  # Just get version, don't launch
        service = Service(CHROMEDRIVER_PATH)
        print(f"✓ ChromeDriver service created: {CHROMEDRIVER_PATH}")
        return True
        
    except Exception as e:
        print(f"✗ ChromeDriver error: {e}")
        return False

if __name__ == "__main__":
    print("=== MAP Case Summarizer Debug Test ===")
    
    db_ok = test_db_connection()
    chrome_ok = test_chromedriver()
    
    if db_ok and chrome_ok:
        print("\n✓ All tests passed! The script should work.")
    else:
        print("\n✗ Some tests failed. Check the errors above.")
        sys.exit(1)
