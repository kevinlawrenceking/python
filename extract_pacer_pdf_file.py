"""
PACER PDF File Download Script

PURPOSE:
This script downloads actual PDF files from PACER using previously extracted metadata.
It processes documents marked as "pending" in the database and downloads them to the 
file system, then updates their status to reflect successful download.

WORKFLOW:
1. Retrieves PACER login credentials from the tools table
2. Queries for pending documents associated with the specified case event
3. Logs into PACER using Selenium WebDriver with download preferences
4. Iterates through each pending document:
   - Navigates to the stored PDF URL
   - Allows browser to download the PDF automatically
   - Creates appropriate directory structure (cases/[case_id]/E[doc_id].pdf)
   - Updates database record with file path and download timestamp

INPUT:
- case_event_id (GUID): ID of the specific case event to process

OUTPUT:
- Downloads PDF files to: \\10.146.176.84\general\docketwatch\docs\cases\[case_id]\E[doc_id].pdf
- Updates documents table: sets rel_path and date_downloaded fields

DOWNLOAD PROCESS:
- Uses Chrome WebDriver with automatic download configuration
- Downloads to network share: \\10.146.176.84\general\docketwatch\docs\cases
- File naming: E[doc_id].pdf (e.g., E12345.pdf)
- Directory structure: cases/[case_id]/[filename]

ERROR HANDLING:
- Per-document error logging without stopping batch processing
- Database transaction management
- Proper cleanup of WebDriver and database connections
- Comprehensive logging via scraper_base module

DEPENDENCIES:
- Selenium WebDriver (Chrome) with download capabilities
- Network access to shared storage location
- scraper_base module for logging utilities
- Database: SQL Server via pyodbc
"""

import sys, argparse, pyodbc, os, time, traceback, zipfile, re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from scraper_base import log_message, setup_logging, get_db_cursor, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"

def main():
    parser = argparse.ArgumentParser(description="Download PACER PDF using stored pdf_url")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    try:
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        log_message(cursor, fk_task_run, "INFO", f"Processing case_event_id: {args.case_event_id}")

        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in DB.")
            return
        USERNAME, PASSWORD, LOGIN_URL = row
        log_message(cursor, fk_task_run, "INFO", f"Retrieved PACER credentials for login URL: {LOGIN_URL}")

        cursor.execute("""
            SELECT c.id AS fk_case,
                   d.doc_id,
                   d.doc_uid,
                   d.pdf_url,
                   d.pdf_type,
                   d.pdf_title
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
            INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            WHERE d.fk_case_event = ? AND d.rel_path = 'pending'
        """, (args.case_event_id,))
        rows = cursor.fetchall()
        if not rows:
            log_message(cursor, fk_task_run, "INFO", "No pending documents to download.")
            return
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(rows)} pending documents to download")

        log_message(cursor, fk_task_run, "INFO", "Initializing Chrome WebDriver")
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        # Remove automatic download preferences - we'll handle downloads manually
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        wait = WebDriverWait(driver, 15)
        log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver initialized")

        log_message(cursor, fk_task_run, "INFO", "Starting PACER login process")
        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.NAME, "loginForm:loginName"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
        try:
            driver.find_element(By.NAME, "loginForm:clientCode").send_keys("DocketWatch")
            log_message(cursor, fk_task_run, "INFO", "Client code 'DocketWatch' entered")
        except:
            log_message(cursor, fk_task_run, "INFO", "Client code field not found - skipping")
        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        time.sleep(3)
        log_message(cursor, fk_task_run, "INFO", "PACER login completed successfully")

        successful_downloads = 0
        failed_downloads = 0

        for i, row in enumerate(rows, 1):
            doc_id = row.doc_id
            doc_uid = row.doc_uid
            pdf_url = row.pdf_url
            fk_case = row.fk_case
            pdf_type = row.pdf_type
            pdf_title = row.pdf_title
            filename = f"E{doc_id}.pdf"
            case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
            os.makedirs(case_dir, exist_ok=True)
            dest_path = os.path.join(case_dir, filename)

            log_message(cursor, fk_task_run, "INFO", 
                f"Processing document {i}/{len(rows)}: {pdf_type} - {pdf_title[:50]}{'...' if len(pdf_title) > 50 else ''}")
            log_message(cursor, fk_task_run, "INFO", f"Document ID: {doc_id}, Case: {fk_case}, Filename: {filename}")

            try:
                log_message(cursor, fk_task_run, "INFO", f"Downloading PDF from: {pdf_url}")
                
                # Use WebDriver to navigate to PDF URL and handle CSRF
                driver.get(pdf_url)
                time.sleep(2)
                
                # Check if we got a CSRF protection page
                if "referrer_form" in driver.page_source and "csrf" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "CSRF protection page detected - submitting form")
                    
                    # Click the Continue link or submit the form
                    try:
                        # Try to find and click the Continue link
                        continue_link = driver.find_element(By.XPATH, "//a[contains(@onclick, 'referrer_form')]")
                        continue_link.click()
                        log_message(cursor, fk_task_run, "INFO", "Continue link clicked")
                    except:
                        # Alternative: submit the form directly
                        form = driver.find_element(By.ID, "referrer_form")
                        form.submit()
                        log_message(cursor, fk_task_run, "INFO", "CSRF form submitted")
                    
                    time.sleep(3)  # Wait for redirect
                
                # Check if we got a PACER billing confirmation page
                if "View Document" in driver.page_source and "PACER Service Center" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "PACER billing confirmation page detected - clicking View Document")
                    
                    try:
                        # Wait for the page to fully load
                        time.sleep(2)
                        
                        # Try multiple selectors for the View Document button
                        view_doc_button = None
                        selectors = [
                            "//input[@value='View Document']",
                            "//input[@type='submit' and @value='View Document']",
                            "//input[contains(@value, 'View Document')]",
                            "//form//input[@type='submit']"
                        ]
                        
                        for selector in selectors:
                            try:
                                view_doc_button = driver.find_element(By.XPATH, selector)
                                if view_doc_button:
                                    log_message(cursor, fk_task_run, "INFO", f"Found View Document button with selector: {selector}")
                                    break
                            except:
                                continue
                        
                        if view_doc_button:
                            # Scroll to the button to ensure it's visible
                            driver.execute_script("arguments[0].scrollIntoView(true);", view_doc_button)
                            time.sleep(1)
                            
                            # Try clicking the button
                            try:
                                view_doc_button.click()
                                log_message(cursor, fk_task_run, "INFO", "View Document button clicked successfully")
                            except:
                                # If regular click fails, try JavaScript click
                                driver.execute_script("arguments[0].click();", view_doc_button)
                                log_message(cursor, fk_task_run, "INFO", "View Document button clicked via JavaScript")
                            
                            # Wait for the PDF to load or page to change
                            time.sleep(5)
                            
                            # Check if we successfully navigated away from the billing page
                            if "PACER Service Center" not in driver.page_source:
                                log_message(cursor, fk_task_run, "INFO", "Successfully navigated away from billing page")
                            else:
                                log_message(cursor, fk_task_run, "WARNING", "Still on billing page after clicking View Document")
                        else:
                            log_message(cursor, fk_task_run, "ERROR", "Could not find View Document button with any selector")
                            failed_downloads += 1
                            continue
                            
                    except Exception as e:
                        log_message(cursor, fk_task_run, "ERROR", f"Failed to handle billing page: {str(e)}")
                        failed_downloads += 1
                        continue
                
                # Now get the current page info
                current_url = driver.current_url
                log_message(cursor, fk_task_run, "INFO", f"Current URL after navigation: {current_url}")
                
                # Check if we're on a PDF page or if we need to wait for PDF download
                page_source = driver.page_source
                
                # If we're still on an HTML page, it might be a PDF loading page
                if "<!DOCTYPE html>" in page_source or "<html>" in page_source:
                    log_message(cursor, fk_task_run, "INFO", "Still on HTML page, checking for PDF content or download")
                    
                    # Wait a bit more for potential PDF load
                    time.sleep(5)
                    
                    # Try to get PDF content via page source or check for PDF iframe
                    try:
                        # Check if there's a PDF iframe or object
                        pdf_elements = driver.find_elements(By.XPATH, "//iframe | //object[@type='application/pdf'] | //embed[@type='application/pdf']")
                        if pdf_elements:
                            log_message(cursor, fk_task_run, "INFO", "Found PDF element on page")
                            # Try to get the PDF src
                            for element in pdf_elements:
                                src = element.get_attribute('src') or element.get_attribute('data')
                                if src:
                                    log_message(cursor, fk_task_run, "INFO", f"Found PDF source: {src}")
                                    current_url = src
                                    break
                    except:
                        pass
                
                # Use current driver context to get PDF content
                try:
                    # Navigate to current URL to ensure we have the latest content
                    if current_url != driver.current_url:
                        driver.get(current_url)
                        time.sleep(3)
                    
                    # Get page source - if it's a PDF, this should be binary content
                    page_source = driver.page_source
                    
                    # Check if we actually got a PDF by looking at the page
                    if "<!DOCTYPE html>" not in page_source and "<html>" not in page_source:
                        log_message(cursor, fk_task_run, "INFO", "Page appears to be PDF content")
                        
                        # Use requests to get the actual PDF binary data
                        cookies = driver.get_cookies()
                        session = requests.Session()
                        for cookie in cookies:
                            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                        
                        headers = {
                            'User-Agent': driver.execute_script("return navigator.userAgent;"),
                            'Referer': pdf_url,
                            'Accept': 'application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        }
                        
                        response = session.get(current_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        
                        # Check if response is actually a PDF
                        content_type = response.headers.get('content-type', '').lower()
                        if 'pdf' in content_type or response.content.startswith(b'%PDF'):
                            # Save PDF content to file
                            with open(dest_path, 'wb') as f:
                                f.write(response.content)
                            
                            file_size = len(response.content)
                            log_message(cursor, fk_task_run, "INFO", f"PDF saved successfully: {filename} ({file_size} bytes)")
                            
                            # Verify file was written correctly
                            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                                log_message(cursor, fk_task_run, "INFO", f"PDF file confirmed on disk: {filename}")
                                
                                rel_path = f"cases\\{fk_case}\\{filename}"
                                cursor.execute("""
                                    UPDATE docketwatch.dbo.documents
                                    SET rel_path = ?, date_downloaded = GETDATE()
                                    WHERE doc_uid = ?
                                """, (rel_path, doc_uid))
                                conn.commit()
                                log_message(cursor, fk_task_run, "INFO", f"Database updated - marked PDF as downloaded: {filename}")
                                successful_downloads += 1
                            else:
                                log_message(cursor, fk_task_run, "ERROR", f"PDF file not properly saved: {dest_path}")
                                failed_downloads += 1
                        else:
                            log_message(cursor, fk_task_run, "ERROR", f"Response is not a PDF. Content-Type: {content_type}")
                            # Save response content for debugging
                            debug_path = dest_path.replace('.pdf', '_debug.html')
                            with open(debug_path, 'wb') as f:
                                f.write(response.content)
                            log_message(cursor, fk_task_run, "INFO", f"Saved debug content to: {debug_path}")
                            failed_downloads += 1
                    else:
                        log_message(cursor, fk_task_run, "ERROR", "Still getting HTML page instead of PDF")
                        # Save page source for debugging
                        debug_path = dest_path.replace('.pdf', '_debug.html')
                        with open(debug_path, 'w', encoding='utf-8') as f:
                            f.write(page_source)
                        log_message(cursor, fk_task_run, "INFO", f"Saved debug content to: {debug_path}")
                        failed_downloads += 1
                        
                except Exception as e:
                    log_message(cursor, fk_task_run, "ERROR", f"Error processing PDF content: {str(e)}")
                    failed_downloads += 1

        log_message(cursor, fk_task_run, "INFO", 
            f"Download process completed. Success: {successful_downloads}, Failed: {failed_downloads}")

    except Exception as e:
        log_message(cursor, None, "ERROR", f"Unhandled error: {str(e)}")
        traceback.print_exc()
    finally:
        if 'driver' in locals():
            driver.quit()
            log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver closed")
        if 'conn' in locals():
            conn.close()
            log_message(cursor, fk_task_run, "INFO", "Database connection closed")

if __name__ == "__main__":
    main()
