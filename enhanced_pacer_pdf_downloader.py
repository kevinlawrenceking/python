#!/usr/bin/env python3
"""
Enhanced PACER PDF Downloader with Redisplay Error Handling

PURPOSE:
This enhanced script handles PACER's "Cannot redisplay" error by implementing
session management and alternative download strategies when documents have
already been accessed.

ENHANCEMENTS:
- Detects "Cannot redisplay" errors from PACER
- Implements fresh session creation for previously accessed documents
- Uses alternative download methods when standard approach fails
- Better error logging and recovery strategies
"""

import sys, argparse, pyodbc, os, time, traceback, zipfile, re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import logging function
sys.path.append(r'\\10.146.176.84\general\docketwatch\python')
from scraper_base import log_message

def detect_pacer_error(driver):
    """
    Detect various PACER error conditions including redisplay errors.
    
    Returns:
        tuple: (error_type, error_message)
        error_type can be: 'redisplay', 'access_denied', 'login_required', 'billing_error', None
    """
    page_source = driver.page_source.lower()
    current_url = driver.current_url.lower()
    
    # Check for redisplay error
    redisplay_indicators = [
        'cannot redisplay',
        'already been shown',
        'document has been accessed',
        'tmp/file',
        'previously displayed'
    ]
    
    for indicator in redisplay_indicators:
        if indicator in page_source:
            return ('redisplay', f"PACER redisplay error detected: {indicator}")
    
    # Check for access denied
    if 'access denied' in page_source or 'not authorized' in page_source:
        return ('access_denied', "Access denied to document")
    
    # Check for login required
    if 'login' in current_url or 'please log in' in page_source:
        return ('login_required', "Login required")
    
    # Check for billing errors
    if 'billing error' in page_source or 'payment required' in page_source:
        return ('billing_error', "Billing error encountered")
    
    return (None, None)

def create_fresh_driver_session():
    """
    Create a completely fresh WebDriver session with new profile.
    This helps avoid PACER's session-based restrictions.
    """
    download_dir = r"\\10.146.176.84\general\docketwatch\docs\cases"
    
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Create unique profile directory to avoid session conflicts
    import tempfile
    profile_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    
    # Set download preferences
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
        "plugins.plugins_disabled": ["Chrome PDF Viewer"]
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver, profile_dir
    except Exception as e:
        print(f"Failed to create WebDriver: {e}")
        return None, None

def handle_redisplay_error(cursor, fk_task_run, pdf_url, doc_id, case_id):
    """
    Handle PACER redisplay error by creating a fresh session and trying alternative methods.
    
    Args:
        cursor: Database cursor
        fk_task_run: Task run ID
        pdf_url: Original PDF URL
        doc_id: Document ID
        case_id: Case ID
    
    Returns:
        tuple: (success, file_path, error_message)
    """
    log_message(cursor, fk_task_run, "WARNING", f"Handling redisplay error for doc {doc_id}")
    
    # Strategy 1: Create completely fresh session
    fresh_driver, profile_dir = create_fresh_driver_session()
    if not fresh_driver:
        return (False, None, "Failed to create fresh WebDriver session")
    
    try:
        # Log in with fresh session
        login_success = login_to_pacer(fresh_driver, cursor, fk_task_run)
        if not login_success:
            return (False, None, "Failed to login with fresh session")
        
        # Try accessing the document again
        fresh_driver.get(pdf_url)
        time.sleep(3)
        
        # Check for errors again
        error_type, error_msg = detect_pacer_error(fresh_driver)
        if error_type == 'redisplay':
            log_message(cursor, fk_task_run, "ERROR", f"Redisplay error persists even with fresh session: {error_msg}")
            
            # Strategy 2: Try to find alternative access method
            # Look for docket entry page instead of direct PDF link
            alt_success, alt_path = try_alternative_access(fresh_driver, cursor, fk_task_run, doc_id, case_id)
            if alt_success:
                return (True, alt_path, None)
            else:
                return (False, None, "Document cannot be accessed - PACER restriction")
        
        # If no redisplay error, proceed with normal download
        return download_pdf_from_driver(fresh_driver, cursor, fk_task_run, doc_id, case_id)
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Exception in redisplay error handler: {str(e)}")
        return (False, None, str(e))
    finally:
        try:
            fresh_driver.quit()
            # Clean up temporary profile directory
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
        except:
            pass

def try_alternative_access(driver, cursor, fk_task_run, doc_id, case_id):
    """
    Try alternative methods to access the document when direct PDF link fails.
    
    This might include:
    - Going to the docket page and finding the document there
    - Looking for alternative download links
    - Using document metadata to construct new URLs
    """
    log_message(cursor, fk_task_run, "INFO", f"Trying alternative access for doc {doc_id}")
    
    try:
        # Get document metadata from database to find alternative paths
        cursor.execute("""
            SELECT pdf_url, case_no, document_number, docket_entry_id
            FROM docketwatch.dbo.documents 
            WHERE id = ?
        """, (doc_id,))
        
        doc_info = cursor.fetchone()
        if not doc_info:
            return (False, None)
        
        pdf_url, case_no, doc_number, docket_entry_id = doc_info
        
        # Strategy: Navigate to docket page and find document link there
        if case_no and doc_number:
            # Construct docket page URL
            court_code = extract_court_code_from_url(pdf_url)
            if court_code:
                docket_url = f"https://ecf.{court_code}.uscourts.gov/cgi-bin/DktRpt.pl?{case_no}"
                log_message(cursor, fk_task_run, "INFO", f"Trying docket page: {docket_url}")
                
                driver.get(docket_url)
                time.sleep(3)
                
                # Look for the specific document number
                doc_links = driver.find_elements(By.XPATH, f"//a[contains(@href, '{doc_number}')]")
                for link in doc_links:
                    href = link.get_attribute('href')
                    if 'doc1' in href or 'pdf' in href.lower():
                        log_message(cursor, fk_task_run, "INFO", f"Found alternative document link: {href}")
                        
                        # Try this link
                        driver.get(href)
                        time.sleep(3)
                        
                        error_type, _ = detect_pacer_error(driver)
                        if error_type != 'redisplay':
                            # Success! Try to download
                            return download_pdf_from_driver(driver, cursor, fk_task_run, doc_id, case_id)
        
        return (False, None)
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Alternative access failed: {str(e)}")
        return (False, None)

def extract_court_code_from_url(url):
    """Extract court code from PACER URL"""
    import re
    match = re.search(r'ecf\.([^.]+)\.uscourts\.gov', url)
    return match.group(1) if match else None

def login_to_pacer(driver, cursor, fk_task_run):
    """Login to PACER with enhanced error checking"""
    try:
        # Get credentials from database
        cursor.execute("SELECT username, pass FROM docketwatch.dbo.tools WHERE id = 2")
        cred_row = cursor.fetchone()
        if not cred_row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found")
            return False
        
        username, password = cred_row
        LOGIN_URL = "https://pacer.login.uscourts.gov/csologin/login.jsf"
        
        driver.get(LOGIN_URL)
        time.sleep(2)
        
        # Fill in credentials
        username_field = driver.find_element(By.ID, "loginForm:loginName")
        password_field = driver.find_element(By.ID, "loginForm:password")
        login_button = driver.find_element(By.ID, "loginForm:loginButton")
        
        username_field.clear()
        username_field.send_keys(username)
        password_field.clear()
        password_field.send_keys(password)
        login_button.click()
        
        time.sleep(3)
        
        # Check if login was successful
        if "Client Code" in driver.page_source or "PACER" in driver.title:
            log_message(cursor, fk_task_run, "INFO", "PACER login successful")
            return True
        else:
            log_message(cursor, fk_task_run, "ERROR", "PACER login failed")
            return False
            
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"PACER login error: {str(e)}")
        return False

def download_pdf_from_driver(driver, cursor, fk_task_run, doc_id, case_id):
    """
    Download PDF from current driver state and save to file system.
    
    Returns:
        tuple: (success, file_path, error_message)
    """
    try:
        # Handle any billing confirmations
        if "View Document" in driver.page_source and "PACER Service Center" in driver.page_source:
            view_doc_button = driver.find_element(By.XPATH, "//input[@value='View Document']")
            if view_doc_button:
                view_doc_button.click()
                time.sleep(5)
        
        # Get current page content
        current_url = driver.current_url
        
        # Use requests session with cookies from driver to download
        cookies = driver.get_cookies()
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        # Download the PDF
        response = session.get(current_url, stream=True)
        if response.status_code == 200:
            # Determine file path
            dest_dir = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}"
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, f"E{doc_id}.pdf")
            
            # Save PDF
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify file was saved
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                log_message(cursor, fk_task_run, "INFO", f"PDF successfully downloaded: {dest_path}")
                return (True, dest_path, None)
            else:
                return (False, None, "PDF file not properly saved")
        else:
            return (False, None, f"HTTP {response.status_code} error downloading PDF")
            
    except Exception as e:
        return (False, None, f"Download error: {str(e)}")

def enhanced_pdf_download(case_event_id):
    """
    Main function with enhanced error handling for PACER redisplay errors.
    """
    print(f"Enhanced PACER PDF Downloader starting for case_event_id: {case_event_id}")
    
    # Database connection
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        fk_task_run = 0  # Default task run
    except Exception as e:
        print(f"Database connection error: {e}")
        return
    
    try:
        # Get pending documents for this case event
        cursor.execute("""
            SELECT id, pdf_url, fk_cases 
            FROM docketwatch.dbo.documents 
            WHERE fk_case_event = ? AND status = 'pending'
        """, (case_event_id,))
        
        pending_docs = cursor.fetchall()
        
        if not pending_docs:
            log_message(cursor, fk_task_run, "INFO", "No pending documents found for this case event")
            return
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(pending_docs)} pending documents")
        
        # Create initial WebDriver session
        driver, profile_dir = create_fresh_driver_session()
        if not driver:
            log_message(cursor, fk_task_run, "ERROR", "Failed to create WebDriver")
            return
        
        try:
            # Login to PACER
            login_success = login_to_pacer(driver, cursor, fk_task_run)
            if not login_success:
                log_message(cursor, fk_task_run, "ERROR", "Failed to login to PACER")
                return
            
            # Process each document
            for doc_id, pdf_url, case_id in pending_docs:
                log_message(cursor, fk_task_run, "INFO", f"Processing document {doc_id}: {pdf_url}")
                
                try:
                    # Navigate to PDF URL
                    driver.get(pdf_url)
                    time.sleep(3)
                    
                    # Check for PACER errors
                    error_type, error_msg = detect_pacer_error(driver)
                    
                    if error_type == 'redisplay':
                        log_message(cursor, fk_task_run, "WARNING", f"Redisplay error detected: {error_msg}")
                        
                        # Use enhanced error handling
                        success, file_path, err_msg = handle_redisplay_error(
                            cursor, fk_task_run, pdf_url, doc_id, case_id
                        )
                        
                        if success:
                            # Update database
                            cursor.execute("""
                                UPDATE docketwatch.dbo.documents 
                                SET status = 'downloaded', rel_path = ?, date_downloaded = GETDATE()
                                WHERE id = ?
                            """, (file_path, doc_id))
                            conn.commit()
                            log_message(cursor, fk_task_run, "INFO", f"Document {doc_id} successfully downloaded via alternative method")
                        else:
                            # Mark as failed with specific error
                            cursor.execute("""
                                UPDATE docketwatch.dbo.documents 
                                SET status = 'failed', error_message = ?
                                WHERE id = ?
                            """, (err_msg or "Redisplay error - cannot access", doc_id))
                            conn.commit()
                            log_message(cursor, fk_task_run, "ERROR", f"Document {doc_id} failed: {err_msg}")
                    
                    elif error_type:
                        log_message(cursor, fk_task_run, "ERROR", f"PACER error for doc {doc_id}: {error_msg}")
                        cursor.execute("""
                            UPDATE docketwatch.dbo.documents 
                            SET status = 'failed', error_message = ?
                            WHERE id = ?
                        """, (error_msg, doc_id))
                        conn.commit()
                    
                    else:
                        # No error detected, proceed with normal download
                        success, file_path, err_msg = download_pdf_from_driver(
                            driver, cursor, fk_task_run, doc_id, case_id
                        )
                        
                        if success:
                            cursor.execute("""
                                UPDATE docketwatch.dbo.documents 
                                SET status = 'downloaded', rel_path = ?, date_downloaded = GETDATE()
                                WHERE id = ?
                            """, (file_path, doc_id))
                            conn.commit()
                            log_message(cursor, fk_task_run, "INFO", f"Document {doc_id} successfully downloaded")
                        else:
                            cursor.execute("""
                                UPDATE docketwatch.dbo.documents 
                                SET status = 'failed', error_message = ?
                                WHERE id = ?
                            """, (err_msg, doc_id))
                            conn.commit()
                            log_message(cursor, fk_task_run, "ERROR", f"Document {doc_id} failed: {err_msg}")
                
                except Exception as e:
                    log_message(cursor, fk_task_run, "ERROR", f"Exception processing doc {doc_id}: {str(e)}")
                    cursor.execute("""
                        UPDATE docketwatch.dbo.documents 
                        SET status = 'failed', error_message = ?
                        WHERE id = ?
                    """, (str(e), doc_id))
                    conn.commit()
        
        finally:
            try:
                driver.quit()
                # Clean up profile directory
                import shutil
                shutil.rmtree(profile_dir, ignore_errors=True)
            except:
                pass
    
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Main process error: {str(e)}")
    
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python enhanced_pacer_pdf_downloader.py <case_event_id>")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    enhanced_pdf_download(case_event_id)
