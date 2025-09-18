#!/usr/bin/env python3
"""
Debug script to test RSS trigger dependencies and basic functionality
"""
import sys
import os

print("=== Testing RSS Trigger Dependencies ===")

# Test basic imports
try:
    import pyodbc
    print("✓ pyodbc imported successfully")
except ImportError as e:
    print(f"✗ pyodbc import failed: {e}")

try:
    import requests
    print("✓ requests imported successfully")
except ImportError as e:
    print(f"✗ requests import failed: {e}")

try:
    from bs4 import BeautifulSoup
    print("✓ BeautifulSoup imported successfully")
except ImportError as e:
    print(f"✗ BeautifulSoup import failed: {e}")

try:
    from scraper_base import log_message
    print("✓ scraper_base.log_message imported successfully")
except ImportError as e:
    print(f"✗ scraper_base.log_message import failed: {e}")

try:
    from error_notification_system import create_error_notifier
    print("✓ error_notification_system.create_error_notifier imported successfully")
except ImportError as e:
    print(f"✗ error_notification_system import failed: {e}")

# Test database connection
print("\n=== Testing Database Connection ===")
try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    print("✓ Database connection successful")
    
    # Test a simple query
    cursor.execute("SELECT TOP 1 1 as test")
    result = cursor.fetchone()
    if result:
        print("✓ Basic query executed successfully")
    
    cursor.close()
    conn.close()
    print("✓ Database connection closed cleanly")
    
except Exception as e:
    print(f"✗ Database connection failed: {e}")

# Test file paths
print("\n=== Testing File Paths ===")
script_filename = os.path.splitext(os.path.basename("docketwatch_rss_trigger.py"))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"

try:
    log_dir = os.path.dirname(LOG_FILE)
    if os.path.exists(log_dir):
        print(f"✓ Log directory exists: {log_dir}")
    else:
        print(f"✗ Log directory missing: {log_dir}")
        
    # Test if we can write to log file
    with open(LOG_FILE, 'a') as f:
        f.write(f"DEBUG TEST: {sys.version}\n")
    print(f"✓ Can write to log file: {LOG_FILE}")
    
except Exception as e:
    print(f"✗ Log file access failed: {e}")

print("\n=== Debug Test Complete ===")