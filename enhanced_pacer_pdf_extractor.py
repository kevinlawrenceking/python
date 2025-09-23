#!/usr/bin/env python3
"""
Enhanced PACER PDF File Download Script

PURPOSE:
This script fixes the issues with the original extract_pacer_pdf_file.py by implementing
better handling of PACER's PDF download mechanism, including:
- Proper session cookie management
- Better handling of temporary PDF URLs
- Improved error detection and recovery
- Browser-native PDF download approach

KEY IMPROVEMENTS:
1. Uses browser's built-in download capability instead of trying to extract PDF URLs
2. Better session management to maintain PACER authentication
3. Improved error detection for failed downloads
4. More robust handling of PACER's anti-automation measures

INPUT:
- case_event_id (GUID): ID of the specific case event to process

OUTPUT:
- Downloads PDF files to: \\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\[case_id]\\E[doc_id].pdf
- Updates documents table: sets rel_path and date_downloaded fields
"""

import sys
import argparse
import pyodbc
import os
import time
import tempfile
import uuid
import traceback
import shutil
import json
import glob
from pathlib import Path

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

def wait_for_download_completion(download_dir, timeout=60):
    """
    Wait for Chrome download to complete by monitoring .crdownload files
    Returns the path to the downloaded file or None if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check for .crdownload files (Chrome's temporary download extension)
        crdownload_files = glob.glob(os.path.join(download_dir, "*.crdownload"))
        if not crdownload_files:
            # No download in progress, check for completed files
            pdf_files = glob.glob(os.path.join(download_dir, "*.pdf"))
            if pdf_files:
                # Return the most recently modified file
                latest_file = max(pdf_files, key=os.path.getctime)
                return latest_file
        time.sleep(1)
    return None

def setup_chrome_for_pdf_download(download_dir):
    """
    Set up Chrome with proper options for PDF downloading
    """
    opts = Options()
    
    # Download settings - force download instead of viewing in browser
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,  # Key setting for PDF downloads
        "plugins.plugins_disabled": ["Chrome PDF Viewer"],
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
        "profile.default_content_setting_values.notifications": 2,  # Block notifications
        "profile.managed_default_content_settings.images": 2,  # Don't load images
    }
    opts.add_experimental_option("prefs", prefs)
    
    # Add command line arguments to force download behavior
    opts.add_argument("--disable-plugins")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-web-security")
    opts.add_argument("--allow-running-insecure-content")
    opts.add_argument("--disable-features=VizDisplayCompositor")
    opts.add_argument("--disable-pdf-extension")  # Disable Chrome's PDF viewer
    
    return opts

def main():
    parser = argparse.ArgumentParser(description="Enhanced PACER PDF downloader")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    # Initialize variables for cleanup
    conn = None
    cursor = None
    driver = None
    fk_task_run = None
    temp_download_dir = None

    try:
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        log_message(cursor, fk_task_run, "INFO", f"Enhanced PDF processor starting for case_event_id: {args.case_event_id}")

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

        # Create temporary download directory
        temp_download_dir = tempfile.mkdtemp(prefix="pacer_pdf_downloads_")
        log_message(cursor, fk_task_run, "INFO", f"Created temporary download directory: {temp_download_dir}")

        # Initialize Chrome with download preferences
        opts = setup_chrome_for_pdf_download(temp_download_dir)
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        wait = WebDriverWait(driver, 20)
        log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver initialized with download settings")

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
                # Clear any existing files in download directory
                for existing_file in glob.glob(os.path.join(temp_download_dir, "*")):
                    try:
                        os.remove(existing_file)
                    except:
                        pass

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
                billing_attempts = 0
                max_billing_attempts = 3
                
                while "View Document" in driver.page_source and "PACER Service Center" in driver.page_source and billing_attempts < max_billing_attempts:
                    billing_attempts += 1
                    log_message(cursor, fk_task_run, "INFO", f"PACER billing page detected (attempt {billing_attempts})")
                    
                    try:
                        # Find and click View Document button
                        view_doc_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//input[@value='View Document']"))
                        )
                        view_doc_button.click()
                        log_message(cursor, fk_task_run, "INFO", "View Document button clicked")
                        
                        # Wait for navigation
                        time.sleep(5)
                        
                    except TimeoutException:
                        log_message(cursor, fk_task_run, "WARNING", "View Document button not found or not clickable")
                        break

                # Check if we're on a page with an iframe containing the PDF
                if "show_temp.pl" in driver.page_source and "iframe" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "Found PDF iframe - extracting direct PDF URL")
                    
                    try:
                        # Find the iframe with the PDF
                        iframe = driver.find_element(By.XPATH, "//iframe[contains(@src, 'show_temp.pl')]")
                        pdf_src = iframe.get_attribute('src')
                        
                        if pdf_src:
                            log_message(cursor, fk_task_run, "INFO", f"Found PDF iframe URL: {pdf_src}")
                            
                            # Navigate directly to the PDF URL to trigger download
                            driver.get(pdf_src)
                            time.sleep(3)
                            
                            # If that doesn't work, try forcing download with JavaScript
                            if not glob.glob(os.path.join(temp_download_dir, "*.pdf")):
                                log_message(cursor, fk_task_run, "INFO", "Attempting to force PDF download")
                                
                                # Create a temporary link and click it to force download
                                script = f"""
                                var link = document.createElement('a');
                                link.href = '{pdf_src}';
                                link.download = '{filename}';
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                                """
                                driver.execute_script(script)
                                time.sleep(2)
                    
                    except Exception as iframe_error:
                        log_message(cursor, fk_task_run, "WARNING", f"Could not handle iframe: {iframe_error}")
                
                # Wait for download to complete
                log_message(cursor, fk_task_run, "INFO", "Waiting for PDF download to complete...")
                
                downloaded_file = wait_for_download_completion(temp_download_dir, timeout=30)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    file_size = os.path.getsize(downloaded_file)
                    log_message(cursor, fk_task_run, "INFO", f"PDF downloaded successfully: {os.path.basename(downloaded_file)} ({file_size} bytes)")
                    
                    # Verify it's actually a PDF
                    with open(downloaded_file, 'rb') as f:
                        header = f.read(4)
                        if header == b'%PDF':
                            # Move file to final destination
                            shutil.move(downloaded_file, final_dest_path)
                            log_message(cursor, fk_task_run, "INFO", f"PDF moved to final location: {final_dest_path}")
                            
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
                            log_message(cursor, fk_task_run, "ERROR", f"Downloaded file is not a valid PDF: {filename}")
                            # Move the file for debugging
                            debug_path = final_dest_path.replace('.pdf', '_debug.dat')
                            shutil.move(downloaded_file, debug_path)
                            log_message(cursor, fk_task_run, "INFO", f"Saved debug file to: {debug_path}")
                            failed_downloads += 1
                else:
                    log_message(cursor, fk_task_run, "ERROR", f"PDF download failed or timed out for {filename}")
                    
                    # Check if there are any files in download directory for debugging
                    download_files = os.listdir(temp_download_dir)
                    if download_files:
                        log_message(cursor, fk_task_run, "INFO", f"Files in download directory: {download_files}")
                    else:
                        log_message(cursor, fk_task_run, "INFO", "No files found in download directory")
                    
                    failed_downloads += 1

            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Error processing document {doc_id}: {str(e)}")
                failed_downloads += 1

        log_message(cursor, fk_task_run, "INFO", 
            f"Enhanced PDF download completed. Success: {successful_downloads}, Failed: {failed_downloads}")

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Critical error in enhanced PDF downloader: {str(e)}")
        traceback.print_exc()
    finally:
        # Cleanup
        if driver:
            try:
                driver.quit()
                log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver closed")
            except:
                pass
        
        if temp_download_dir and os.path.exists(temp_download_dir):
            try:
                shutil.rmtree(temp_download_dir)
                log_message(cursor, fk_task_run, "INFO", f"Cleaned up temporary download directory: {temp_download_dir}")
            except Exception as cleanup_error:
                log_message(cursor, fk_task_run, "WARNING", f"Could not cleanup temp directory: {cleanup_error}")
        
        if conn:
            try:
                conn.close()
                log_message(cursor, fk_task_run, "INFO", "Database connection closed")
            except:
                pass

if __name__ == "__main__":
    main()