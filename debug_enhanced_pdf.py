#!/usr/bin/env python3
"""
Debug Enhanced PDF Downloader Issues
Find out why the enhanced downloader is aborting silently.
"""

import sys
import traceback

def debug_enhanced_downloader(case_event_id):
    """Debug why enhanced downloader is failing"""
    
    print("🔍 DEBUGGING ENHANCED PDF DOWNLOADER")
    print(f"Case Event ID: {case_event_id}")
    print("=" * 50)
    
    # Test 1: Basic imports
    print("\n1️⃣ Testing basic imports...")
    try:
        import pyodbc
        print("✅ pyodbc import OK")
    except Exception as e:
        print(f"❌ pyodbc import failed: {e}")
        return
    
    try:
        import requests
        print("✅ requests import OK")
    except Exception as e:
        print(f"❌ requests import failed: {e}")
        return
    
    # Test 2: Selenium imports (likely culprit)
    print("\n2️⃣ Testing Selenium imports...")
    try:
        from selenium import webdriver
        print("✅ selenium.webdriver import OK")
    except Exception as e:
        print(f"❌ selenium.webdriver import failed: {e}")
        print("This is likely the issue - Selenium may not be installed or configured correctly")
        return
    
    try:
        from selenium.webdriver.chrome.options import Options
        print("✅ selenium Chrome options import OK")
    except Exception as e:
        print(f"❌ selenium Chrome options import failed: {e}")
        return
    
    # Test 3: Database connection
    print("\n3️⃣ Testing database connection...")
    try:
        import pyodbc
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        print("✅ Database connection OK")
        
        # Test case event exists
        cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.case_events WHERE id = ?", (case_event_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"✅ Case event {case_event_id} found")
        else:
            print(f"❌ Case event {case_event_id} not found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Test 4: Chrome WebDriver setup
    print("\n4️⃣ Testing Chrome WebDriver setup...")
    try:
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run headless for testing
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        print("✅ Chrome options configured")
        
        # Try to create WebDriver (this often fails)
        try:
            driver = webdriver.Chrome(options=chrome_options)
            print("✅ Chrome WebDriver created successfully")
            driver.quit()
        except Exception as e:
            print(f"❌ Chrome WebDriver creation failed: {e}")
            print("This is likely the main issue - ChromeDriver may not be installed or in PATH")
            
            # Suggest solutions
            print("\n💡 POTENTIAL SOLUTIONS:")
            print("1. Install ChromeDriver and add to PATH")
            print("2. Specify ChromeDriver path explicitly")
            print("3. Use original PDF downloader instead")
            return
            
    except Exception as e:
        print(f"❌ Chrome setup failed: {e}")
        return
    
    print("\n✅ All basic tests passed - enhanced downloader should work")
    
    # Test 5: Try importing the enhanced downloader module
    print("\n5️⃣ Testing enhanced downloader import...")
    try:
        # Add current directory to path
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        import enhanced_pacer_pdf_downloader
        print("✅ Enhanced downloader module imported successfully")
        
        # Try calling the main function
        print("\n6️⃣ Testing enhanced downloader execution...")
        try:
            result = enhanced_pacer_pdf_downloader.enhanced_pdf_download(case_event_id)
            print(f"✅ Enhanced downloader executed: {result}")
        except Exception as e:
            print(f"❌ Enhanced downloader execution failed: {e}")
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Enhanced downloader import failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_enhanced_pdf.py <case_event_id>")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    debug_enhanced_downloader(case_event_id)
