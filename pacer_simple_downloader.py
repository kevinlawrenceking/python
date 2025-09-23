#!/usr/bin/env python3
"""
PACER Simple PDF Downloader - No BS approach

This script takes the simplest possible approach:
1. Login to PACER
2. Navigate to the document URL
3. Save whatever we get to a file
4. If it's HTML, save it as HTML for debugging
5. If it's PDF, save it as PDF

No fancy detection, no iframe parsing, no button clicking.
Just brute force save whatever PACER gives us.
"""

import sys
import argparse
import pyodbc
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"

def simple_download(case_event_id):
    """Just try to download the damn PDFs without any fancy logic"""
    
    # Get database connection
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    print(f"Processing case_event: {case_event_id}")
    
    # Get pending documents
    cursor.execute("""
        SELECT doc_id, doc_uid, pdf_url, fk_case, pdf_type, pdf_title
        FROM docketwatch.dbo.documents
        WHERE fk_case_event = ? AND rel_path = 'pending'
    """, (case_event_id,))
    
    docs = cursor.fetchall()
    if not docs:
        print("No pending documents found")
        return
    
    print(f"Found {len(docs)} pending documents")
    
    # Get PACER credentials
    cursor.execute("SELECT username, pass FROM dbo.tools WHERE id = 2")
    creds = cursor.fetchone()
    username = creds.username
    password = creds[1]  # Use index since 'pass' is a keyword
    
    # Setup Chrome with downloads
    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    
    # Set download directory
    prefs = {
        "download.default_directory": FINAL_PDF_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.default_content_setting_values.automatic_downloads": 1
    }
    opts.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
    
    try:
        # Login to PACER
        print("Logging into PACER...")
        driver.get("https://pacer.login.uscourts.gov/csologin/login.jsf")
        time.sleep(3)
        
        driver.find_element(By.ID, "loginForm:loginName").send_keys(username)
        driver.find_element(By.ID, "loginForm:password").send_keys(password)
        
        try:
            driver.find_element(By.ID, "loginForm:clientCode").send_keys("DocketWatch")
        except:
            pass
        
        # Try multiple possible login button selectors
        login_clicked = False
        login_selectors = [
            ("ID", "loginForm:loginButton"),
            ("ID", "loginForm:fbtnLogin"), 
            ("NAME", "loginForm:fbtnLogin"),
            ("XPATH", "//input[@type='submit'][@value='Login']"),
            ("XPATH", "//button[contains(text(), 'Login')]"),
            ("XPATH", "//input[contains(@value, 'Login')]")
        ]
        
        for by_type, selector in login_selectors:
            try:
                if by_type == "ID":
                    login_btn = driver.find_element(By.ID, selector)
                elif by_type == "NAME":
                    login_btn = driver.find_element(By.NAME, selector)
                elif by_type == "XPATH":
                    login_btn = driver.find_element(By.XPATH, selector)
                
                login_btn.click()
                print(f"Login button clicked using {by_type}: {selector}")
                login_clicked = True
                break
            except Exception as e:
                print(f"Login selector {by_type}:{selector} failed: {e}")
                continue
        
        if not login_clicked:
            print("ERROR: Could not find any login button")
            return
        time.sleep(5)
        print("Login completed")
        
        # Process each document
        for i, doc in enumerate(docs, 1):
            doc_id = doc.doc_id
            doc_uid = doc.doc_uid
            pdf_url = doc.pdf_url
            fk_case = doc.fk_case
            
            filename = f"E{doc_id}.pdf"
            case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
            os.makedirs(case_dir, exist_ok=True)
            dest_path = os.path.join(case_dir, filename)
            
            print(f"\n[{i}/{len(docs)}] Processing {filename}")
            print(f"URL: {pdf_url}")
            
            try:
                # Just navigate to the URL
                driver.get(pdf_url)
                time.sleep(5)
                
                # Check what we got
                current_url = driver.current_url
                page_source = driver.page_source
                
                print(f"Current URL after navigation: {current_url}")
                print(f"Page title: {driver.title}")
                print(f"Page source length: {len(page_source)} characters")
                
                # Save debug HTML immediately
                debug_path = dest_path.replace('.pdf', '_debug.html')
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {current_url}\n")
                    f.write(f"Title: {driver.title}\n")
                    f.write("=" * 50 + "\n")
                    f.write(page_source)
                
                print(f"Saved debug HTML to: {debug_path}")
                
                # Look for common elements
                if "View Document" in page_source:
                    print("Found 'View Document' button - clicking it")
                    try:
                        view_btn = driver.find_element(By.XPATH, "//input[@value='View Document']")
                        view_btn.click()
                        time.sleep(5)
                        print(f"After clicking View Document: {driver.current_url}")
                        
                        # Save debug HTML after clicking View Document
                        new_page_source = driver.page_source
                        debug_path2 = dest_path.replace('.pdf', '_after_view_debug.html')
                        with open(debug_path2, 'w', encoding='utf-8') as f:
                            f.write(f"URL: {driver.current_url}\n")
                            f.write(f"Title: {driver.title}\n")
                            f.write("=" * 50 + "\n")
                            f.write(new_page_source)
                        print(f"Saved post-View Document debug HTML to: {debug_path2}")
                        
                    except Exception as e:
                        print(f"Could not click View Document: {e}")
                
                # Check if current page looks like a PDF
                if driver.current_url.endswith('.pdf'):
                    print("Current URL ends with .pdf - this might be a direct PDF")
                
                if "iframe" in page_source.lower():
                    print("Found iframe in page source")
                    
                if "show_temp.pl" in page_source:
                    print("Found show_temp.pl in page source")
                
                # Try to save the current page as PDF using browser's print function
                try:
                    # Execute JavaScript to trigger browser's print dialog
                    print("Attempting to save page using browser print...")
                    driver.execute_script("window.print();")
                    time.sleep(3)
                except Exception as e:
                    print(f"Print attempt failed: {e}")
                
                print(f"Completed processing {filename}")
                
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue
    
    finally:
        driver.quit()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple PACER PDF downloader")
    parser.add_argument("case_event_id", help="Case event ID to process")
    args = parser.parse_args()
    
    simple_download(args.case_event_id)