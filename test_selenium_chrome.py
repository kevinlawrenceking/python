#!/usr/bin/env python3
"""
Test script to diagnose Chrome/ChromeDriver issues
This will help identify version mismatches and test different Chrome configurations
"""

import sys
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

def get_chrome_version():
    """Get the installed Chrome version"""
    try:
        import subprocess
        result = subprocess.run([
            'reg', 'query', 
            'HKEY_CURRENT_USER\\SOFTWARE\\Google\\Chrome\\BLBeacon', 
            '/v', 'version'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'version' in line:
                    version = line.split()[-1]
                    return version
    except:
        pass
    
    # Alternative method
    try:
        chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if os.path.exists(chrome_path):
            result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split()[-1]
    except:
        pass
    
    return "Unknown"

def get_chromedriver_version():
    """Get ChromeDriver version"""
    try:
        import subprocess
        result = subprocess.run([CHROMEDRIVER_PATH, '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split()[1]
    except:
        pass
    return "Unknown"

def test_chrome_config(config_name, options):
    """Test a specific Chrome configuration"""
    print(f"\n=== Testing {config_name} ===")
    
    try:
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
        print(f"✅ {config_name}: SUCCESS - Chrome started")
        
        # Test basic navigation
        driver.get("https://www.google.com")
        time.sleep(2)
        
        title = driver.title
        print(f"   Page title: {title}")
        
        driver.quit()
        print(f"   Browser closed successfully")
        return True
        
    except Exception as e:
        print(f"❌ {config_name}: FAILED")
        print(f"   Error: {str(e)}")
        return False

def main():
    print("Chrome/ChromeDriver Diagnostic Tool")
    print("=" * 50)
    
    # Check versions
    chrome_version = get_chrome_version()
    chromedriver_version = get_chromedriver_version()
    
    print(f"Chrome Version: {chrome_version}")
    print(f"ChromeDriver Version: {chromedriver_version}")
    
    # Check if ChromeDriver exists
    if not os.path.exists(CHROMEDRIVER_PATH):
        print(f"❌ ChromeDriver not found at: {CHROMEDRIVER_PATH}")
        return
    
    print(f"✅ ChromeDriver found at: {CHROMEDRIVER_PATH}")
    
    # Test configurations
    configs = []
    
    # Config 1: Minimal (no headless)
    opts1 = Options()
    opts1.add_argument("--no-sandbox")
    opts1.add_argument("--disable-dev-shm-usage")
    configs.append(("Minimal (Visible)", opts1))
    
    # Config 2: Current production settings (headless)
    opts2 = Options()
    opts2.add_argument("--headless=new")
    opts2.add_argument("--disable-gpu")
    opts2.add_argument("--no-sandbox")
    opts2.add_argument("--disable-dev-shm-usage")
    opts2.add_argument("--disable-extensions")
    opts2.add_argument("--disable-plugins")
    opts2.add_argument("--disable-images")
    configs.append(("Production (Headless)", opts2))
    
    # Config 3: Alternative headless
    opts3 = Options()
    opts3.add_argument("--headless")  # Old headless flag
    opts3.add_argument("--no-sandbox")
    opts3.add_argument("--disable-dev-shm-usage")
    opts3.add_argument("--disable-gpu")
    configs.append(("Alternative Headless", opts3))
    
    # Config 4: Safe mode
    opts4 = Options()
    opts4.add_argument("--no-sandbox")
    opts4.add_argument("--disable-dev-shm-usage")
    opts4.add_argument("--disable-gpu")
    opts4.add_argument("--remote-debugging-port=9222")
    configs.append(("Safe Mode (Visible)", opts4))
    
    # Test each configuration
    results = {}
    for config_name, options in configs:
        results[config_name] = test_chrome_config(config_name, options)
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    working_configs = [name for name, success in results.items() if success]
    failed_configs = [name for name, success in results.items() if not success]
    
    if working_configs:
        print("✅ Working configurations:")
        for config in working_configs:
            print(f"   - {config}")
    
    if failed_configs:
        print("❌ Failed configurations:")
        for config in failed_configs:
            print(f"   - {config}")
    
    # Recommendations
    print("\nRECOMMENDations:")
    if "Minimal (Visible)" in working_configs:
        print("✅ Basic Chrome works - ChromeDriver is compatible")
        if "Production (Headless)" not in working_configs:
            print("⚠️  Headless mode is the issue - recommend disabling headless temporarily")
    else:
        print("❌ Chrome/ChromeDriver version mismatch - needs ChromeDriver update")
        print("   Download from: https://chromedriver.chromium.org/")
    
    print(f"\nChrome version: {chrome_version}")
    print(f"ChromeDriver version: {chromedriver_version}")
    
    if chrome_version != "Unknown" and chromedriver_version != "Unknown":
        chrome_major = chrome_version.split('.')[0] if '.' in chrome_version else chrome_version
        driver_major = chromedriver_version.split('.')[0] if '.' in chromedriver_version else chromedriver_version
        
        if chrome_major != driver_major:
            print("⚠️  Major version mismatch detected!")
            print(f"   Need ChromeDriver {chrome_major}.x.x.x")

if __name__ == "__main__":
    main()