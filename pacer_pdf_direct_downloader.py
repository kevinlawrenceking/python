#!/usr/bin/env python3
"""
PACER PDF Direct Download Script

This script specifically handles the PACER iframe PDF scenario where PDFs are
embedded in iframes using show_temp.pl URLs. It directly downloads the PDF
content using requests with the proper session cookies.
"""

import sys
import argparse
import pyodbc
import os
import time
import requests
import tempfile
import uuid
import traceback
import shutil

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from scraper_base import log_message, setup_logging, get_db_cursor, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"

def download_pdf_from_iframe(driver, cursor, fk_task_run):
    """
    Extract and download PDF from PACER iframe
    Returns the PDF content as bytes or None
    """
    try:
        # Look for iframe with show_temp.pl
        iframe = driver.find_element(By.XPATH, "//iframe[contains(@src, 'show_temp.pl')]")
        pdf_url = iframe.get_attribute('src')
        
        if not pdf_url:
            log_message(cursor, fk_task_run, "ERROR", "No PDF URL found in iframe")
            return None
        
        log_message(cursor, fk_task_run, "INFO", f"Found PDF iframe URL: {pdf_url}")
        
        # Convert relative URL to absolute if needed
        if pdf_url.startswith('/'):
            current_url = driver.current_url
            base_url = '/'.join(current_url.split('/')[:3])  # Protocol + domain
            pdf_url = base_url + pdf_url
        
        log_message(cursor, fk_task_run, "INFO", f"Downloading PDF from: {pdf_url}")
        
        # Get cookies from current session
        cookies = {}
        for cookie in driver.get_cookies():
            cookies[cookie['name']] = cookie['value']
        
        # Set up headers to mimic the browser
        headers = {
            'User-Agent': driver.execute_script("return navigator.userAgent;"),
            'Accept': 'application/pdf,application/octet-stream,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': driver.current_url,
        }
        
        # Download the PDF
        response = requests.get(pdf_url, cookies=cookies, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Check if we got a PDF
        content_type = response.headers.get('content-type', '').lower()
        content = response.content
        
        if 'pdf' in content_type or content.startswith(b'%PDF'):
            log_message(cursor, fk_task_run, "INFO", f"Successfully downloaded PDF ({len(content)} bytes)")
            return content
        else:
            log_message(cursor, fk_task_run, "ERROR", f"Response is not a PDF. Content-Type: {content_type}")
            # Log first 200 characters for debugging
            preview = content.decode('utf-8', errors='ignore')[:200]
            log_message(cursor, fk_task_run, "DEBUG", f"Response preview: {preview}")
            return None
    
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Error downloading PDF from iframe: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="PACER PDF direct downloader for iframe scenarios")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    # Initialize variables for cleanup
    conn = None
    cursor = None
    driver = None
    fk_task_run = None

    try:
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        log_message(cursor, fk_task_run, "INFO", f"Direct PDF downloader starting for case_event_id: {args.case_event_id}")

        # Get PACER credentials
        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in tools table")
            return

        username, password, login_url = row
        log_message(cursor, fk_task_run, "INFO", f"Retrieved PACER credentials for login URL: {login_url}")

        # Get pending documents
        cursor.execute("""
            SELECT doc_id, doc_uid, pdf_url, fk_case, pdf_type, pdf_title, rel_path
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ? AND rel_path = 'pending'
            ORDER BY doc_id
        """, (args.case_event_id,))
        
        rows = cursor.fetchall()
        if not rows:
            log_message(cursor, fk_task_run, "INFO", "No pending documents found for case event")
            return

        log_message(cursor, fk_task_run, "INFO", f"Found {len(rows)} pending documents to download")

        # Initialize Chrome (no special download settings needed)
        opts = Options()
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        wait = WebDriverWait(driver, 20)
        log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver initialized")

        # Login to PACER
        log_message(cursor, fk_task_run, "INFO", "Starting PACER login process")
        driver.get(login_url)
        time.sleep(3)

        # Fill login form
        driver.find_element(By.NAME, "loginForm:loginName").send_keys(username)
        driver.find_element(By.NAME, "loginForm:password").send_keys(password)
        
        # Enter client code if field exists
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
            
            # Create case directory
            case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
            os.makedirs(case_dir, exist_ok=True)
            final_dest_path = os.path.join(case_dir, filename)

            log_message(cursor, fk_task_run, "INFO", 
                f"Processing document {i}/{len(rows)}: {pdf_type} - {pdf_title[:50]}{'...' if len(pdf_title) > 50 else ''}")
            log_message(cursor, fk_task_run, "INFO", f"Document ID: {doc_id}, Case: {fk_case}, Filename: {filename}")

            try:
                log_message(cursor, fk_task_run, "INFO", f"Navigating to PDF URL: {pdf_url}")
                
                # Navigate to PDF URL
                driver.get(pdf_url)
                time.sleep(3)

                # Handle CSRF protection if present
                if "referrer_form" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "CSRF protection detected - submitting form")
                    try:
                        form = driver.find_element(By.ID, "referrer_form")
                        form.submit()
                        time.sleep(3)
                    except:
                        try:
                            continue_link = driver.find_element(By.XPATH, "//a[contains(@onclick, 'referrer_form')]")
                            continue_link.click()
                            time.sleep(3)
                        except:
                            log_message(cursor, fk_task_run, "WARNING", "Could not handle CSRF form")

                # Handle PACER billing confirmation
                if "View Document" in driver.page_source and "PACER Service Center" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "PACER billing page detected")
                    
                    try:
                        view_doc_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//input[@value='View Document']"))
                        )
                        view_doc_button.click()
                        log_message(cursor, fk_task_run, "INFO", "View Document button clicked")
                        time.sleep(5)
                        
                    except TimeoutException:
                        log_message(cursor, fk_task_run, "WARNING", "View Document button not found")

                # Now check for iframe with PDF
                if "show_temp.pl" in driver.page_source and "iframe" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "Found PDF iframe - downloading content directly")
                    
                    pdf_content = download_pdf_from_iframe(driver, cursor, fk_task_run)
                    
                    if pdf_content:
                        # Save PDF to file
                        with open(final_dest_path, 'wb') as f:
                            f.write(pdf_content)
                        
                        log_message(cursor, fk_task_run, "INFO", f"PDF saved successfully: {filename} ({len(pdf_content)} bytes)")
                        
                        # Update database
                        rel_path = f"cases\\{fk_case}\\{filename}"
                        cursor.execute("""
                            UPDATE docketwatch.dbo.documents 
                            SET rel_path = ?, date_downloaded = GETDATE()
                            WHERE doc_uid = ?
                        """, (rel_path, doc_uid))
                        conn.commit()
                        
                        log_message(cursor, fk_task_run, "INFO", f"Database updated successfully for {filename}")
                        successful_downloads += 1
                    else:
                        log_message(cursor, fk_task_run, "ERROR", f"Failed to download PDF content for {filename}")
                        failed_downloads += 1
                else:
                    log_message(cursor, fk_task_run, "WARNING", f"No PDF iframe found for {filename}")
                    failed_downloads += 1

            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Error processing document {doc_id}: {str(e)}")
                failed_downloads += 1

        log_message(cursor, fk_task_run, "INFO", 
            f"Direct PDF download completed. Success: {successful_downloads}, Failed: {failed_downloads}")

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Critical error in direct PDF downloader: {str(e)}")
        traceback.print_exc()
    finally:
        # Cleanup
        if driver:
            try:
                driver.quit()
                log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver closed")
            except:
                pass
        
        if conn:
            try:
                conn.close()
                log_message(cursor, fk_task_run, "INFO", "Database connection closed")
            except:
                pass

if __name__ == "__main__":
    main()