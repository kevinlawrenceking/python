#!/usr/bin/env python3
"""
Combined PACER PDF Pr        log_message(cursor, fk_task_run, "INFO", "PACER login completed successfully")
        return True
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"PACER login failed: {str(e)}")
        return False

def discover_missing_event_url(driver, cursor, fk_task_run, case_event_id):
    """
    Discover and populate missing event_url by scraping PACER docket page.
    This handles cases where event_url is NULL but we have basic event info.
    """
    try:
        # Get additional event details for URL construction
        cursor.execute("""
            SELECT e.event_no, e.event_date, e.fk_cases, c.pacer_id, ps.url as pacer_site_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
            WHERE e.id = ?
        """, (case_event_id,))
        
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Could not get event details for {case_event_id}")
        
        event_no, event_date, fk_cases, pacer_id, pacer_site_url = row
        
        if not event_no or not pacer_id:
            raise ValueError(f"Missing event_no ({event_no}) or pacer_id ({pacer_id}) - cannot discover URL")
        
        log_case_message(cursor, fk_task_run, "INFO", 
                       f"Attempting to discover event_url for event_no {event_no} in case {pacer_id}")
        
        # Construct docket report URL to find the event
        docket_url = f"{pacer_site_url}/cgi-bin/DktRpt.pl?{pacer_id}"
        
        driver.get(docket_url)
        time.sleep(3)
        
        # Handle CSRF form if present
        if "referrer_form" in driver.page_source:
            try:
                driver.find_element(By.ID, "referrer_form").submit()
                time.sleep(3)
                log_case_message(cursor, fk_task_run, "INFO", "PACER CSRF form submitted during URL discovery")
            except Exception as e:
                log_case_message(cursor, fk_task_run, "WARNING", f"CSRF form submission failed: {str(e)}")
        
        # Parse the docket page to find the event
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Look for event number in table rows
        event_url_found = None
        for tr in soup.find_all("tr"):
            # Check if this row contains our event number
            cells = tr.find_all("td")
            if len(cells) >= 2:
                # First cell often contains event number
                first_cell_text = cells[0].get_text(strip=True)
                if first_cell_text == str(event_no):
                    # Look for document links in this row
                    for a_tag in tr.find_all("a", href=re.compile(r"doc1")):
                        href = a_tag.get('href')
                        if href:
                            # Construct full URL if relative
                            if not href.startswith("http"):
                                event_url_found = pacer_site_url + href
                            else:
                                event_url_found = href
                            break
                    if event_url_found:
                        break
        
        if event_url_found:
            # Update the database with discovered URL
            cursor.execute("""
                UPDATE docketwatch.dbo.case_events
                SET event_url = ?
                WHERE id = ?
            """, (event_url_found, case_event_id))
            
            log_case_message(cursor, fk_task_run, "INFO", 
                           f"Discovered and updated event_url: {event_url_found}")
            
            return event_url_found
        else:
            log_case_message(cursor, fk_task_run, "WARNING", 
                           f"Could not find document link for event_no {event_no} on docket page")
            return None
            
    except Exception as e:
        log_case_message(cursor, fk_task_run, "ERROR", 
                       f"Failed to discover event_url: {str(e)}")
        return Noner
Combines metadata extraction and PDF download into a single script.

This script:
1. Extracts document metadata from PACER event pages
2. Creates document records in the database
3. Downloads the actual PDF files
4. Updates the database with file paths

INPUT: case_event_id (GUID)
OUTPUT: Downloaded PDFs and updated database records
"""

import sys, argparse, pyodbc, os, time, traceback, zipfile, re
import tempfile
import uuid
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup

from scraper_base import log_message, setup_logging, get_db_cursor, get_task_context_by_tool_id, log_case_message

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"

def login_to_pacer(driver, username, password, login_url, cursor, fk_task_run):
    """Login to PACER with error handling"""
    try:
        log_message(cursor, fk_task_run, "INFO", f"Logging into PACER: {login_url}")
        driver.get(login_url)
        
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.NAME, "loginForm:loginName"))).send_keys(username)
        driver.find_element(By.NAME, "loginForm:password").send_keys(password)
        
        try:
            driver.find_element(By.NAME, "loginForm:clientCode").send_keys("DocketWatch")
            log_message(cursor, fk_task_run, "INFO", "Client code 'DocketWatch' entered")
        except:
            log_message(cursor, fk_task_run, "INFO", "Client code field not found - skipping")
        
        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        time.sleep(3)
        log_message(cursor, fk_task_run, "INFO", "PACER login completed successfully")
        return True
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Login failed: {str(e)}")
        return False

def extract_doc_rows(soup):
    """Extract document rows from PACER page"""
    return [tr for tr in soup.find_all("tr") if tr.find("a", href=re.compile("doc1")) and 'document_' in str(tr)]

def parse_doc_row(tr, base_url, pdf_type, default_pdf_title):
    """Parse a document row and extract metadata"""
    try:
        tds = tr.find_all("td")
        a_tag = tr.find("a", href=re.compile(r'doc1'))
        if not a_tag:
            return None

        pdf_url = a_tag['href']
        if not pdf_url.startswith("http"):
            pdf_url = base_url + pdf_url

        match = re.search(r'/doc1/(\d+)', pdf_url)
        doc_id = int(match.group(1)) if match else None

        pdf_no = int(a_tag.text.strip()) if a_tag.text.strip().isdigit() else 0
        desc = default_pdf_title if pdf_type == "Docket" else " ".join(td.get_text(strip=True) for td in tds[2:4])

        return {
            "doc_id": doc_id,
            "pdf_url": pdf_url,
            "pdf_title": desc,
            "pdf_type": pdf_type,
            "pdf_no": pdf_no,
            "rel_path": "pending"
        }
    except Exception as e:
        return None

def extract_metadata_step(driver, cursor, fk_task_run, case_event_id, case_id, event_url, event_description, base_url):
    """Step 1: Extract document metadata from PACER page"""
    
    log_message(cursor, fk_task_run, "INFO", "=== STEP 1: EXTRACTING METADATA ===")
    
    try:
        # Navigate to the event page
        log_message(cursor, fk_task_run, "INFO", f"Loading event page: {event_url}")
        driver.get(event_url)
        time.sleep(3)

        # Handle CSRF form if present
        if "referrer_form" in driver.page_source:
            try:
                driver.find_element(By.ID, "referrer_form").submit()
                time.sleep(3)
                log_message(cursor, fk_task_run, "INFO", "PACER CSRF form submitted")
            except Exception as e:
                log_message(cursor, fk_task_run, "WARNING", f"CSRF form submission failed: {str(e)}")

        # Parse the page for document links
        soup = BeautifulSoup(driver.page_source, "html.parser")
        doc_rows = extract_doc_rows(soup)
        inserted = 0

        if not doc_rows:
            # Fallback: create record for the event URL itself if it contains a doc1 link
            match = re.search(r'/doc1/(\d+)', event_url)
            if match:
                doc_id = int(match.group(1))
                
                # Check if document already exists and handle accordingly
                cursor.execute("""
                    SELECT doc_uid, rel_path, fk_case 
                    FROM docketwatch.dbo.documents 
                    WHERE doc_id = ?
                """, (doc_id,))
                existing_doc = cursor.fetchone()
                
                if existing_doc:
                    doc_uid, rel_path, existing_fk_case = existing_doc
                    
                    # Check if PDF file actually exists
                    if rel_path and rel_path != 'pending':
                        pdf_filename = f"E{doc_id}.pdf"
                        pdf_full_path = os.path.join(FINAL_PDF_DIR, str(existing_fk_case), pdf_filename)
                        
                        if os.path.exists(pdf_full_path) and os.path.getsize(pdf_full_path) > 1024:
                            log_message(cursor, fk_task_run, "INFO", f"Fallback document {doc_id} already exists with PDF - skipping")
                        else:
                            # Document exists but no PDF - update to pending
                            cursor.execute("""
                                UPDATE docketwatch.dbo.documents 
                                SET fk_case_event = ?, pdf_url = ?, pdf_title = ?, 
                                    pdf_type = 'Docket', pdf_no = 0, rel_path = 'pending', 
                                    date_downloaded = GETDATE()
                                WHERE doc_uid = ?
                            """, (case_event_id, event_url, event_description, doc_uid))
                            inserted = 1
                            log_message(cursor, fk_task_run, "INFO", f"Updated existing fallback document {doc_id}")
                    else:
                        # Document exists but rel_path is pending - update it
                        cursor.execute("""
                            UPDATE docketwatch.dbo.documents 
                            SET fk_case_event = ?, pdf_url = ?, pdf_title = ?, 
                                date_downloaded = GETDATE()
                            WHERE doc_uid = ?
                        """, (case_event_id, event_url, event_description, doc_uid))
                        inserted = 1
                        log_message(cursor, fk_task_run, "INFO", f"Updated existing pending document {doc_id}")
                else:
                    # Document doesn't exist - create new
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'pending', GETDATE())
                    """, (
                        case_id, case_event_id, 2, doc_id, event_url, event_description
                    ))
                    inserted = 1
                    log_message(cursor, fk_task_run, "INFO", f"Inserted new fallback docket PDF {doc_id}")
        else:
            # Process each document row found
            for i, tr in enumerate(doc_rows):
                pdf_type = "Docket" if i == 0 else "Attachment"
                doc_data = parse_doc_row(tr, base_url, pdf_type, event_description)
                
                if not doc_data or not doc_data["doc_id"]:
                    continue
                
                # Check if document already exists and handle accordingly
                cursor.execute("""
                    SELECT doc_uid, rel_path, fk_case 
                    FROM docketwatch.dbo.documents 
                    WHERE doc_id = ?
                """, (doc_data["doc_id"],))
                existing_doc = cursor.fetchone()
                
                if existing_doc:
                    doc_uid, rel_path, existing_fk_case = existing_doc
                    
                    # Check if PDF file actually exists
                    if rel_path and rel_path != 'pending':
                        pdf_filename = f"E{doc_data['doc_id']}.pdf"
                        pdf_full_path = os.path.join(FINAL_PDF_DIR, str(existing_fk_case), pdf_filename)
                        
                        if os.path.exists(pdf_full_path) and os.path.getsize(pdf_full_path) > 1024:
                            log_message(cursor, fk_task_run, "INFO", f"Document {doc_data['doc_id']} already exists with PDF - skipping")
                            continue
                    
                    # Document exists but no PDF file - update existing record
                    cursor.execute("""
                        UPDATE docketwatch.dbo.documents 
                        SET fk_case_event = ?, pdf_url = ?, pdf_title = ?, 
                            pdf_type = ?, pdf_no = ?, rel_path = 'pending', 
                            date_downloaded = GETDATE()
                        WHERE doc_uid = ?
                    """, (
                        case_event_id, doc_data["pdf_url"], doc_data["pdf_title"],
                        doc_data["pdf_type"], doc_data["pdf_no"], doc_uid
                    ))
                    inserted += 1
                    log_message(cursor, fk_task_run, "INFO", f"Updated existing document {doc_data['doc_id']}: {doc_data['pdf_title'][:50]}")
                else:
                    # Document doesn't exist - create new record
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
                    """, (
                        case_id, case_event_id, 2,
                        doc_data["doc_id"], doc_data["pdf_url"],
                        doc_data["pdf_title"], doc_data["pdf_type"],
                        doc_data["pdf_no"], doc_data["rel_path"]
                    ))
                    inserted += 1
                    log_message(cursor, fk_task_run, "INFO", f"Inserted new document {doc_data['doc_id']}: {doc_data['pdf_title'][:50]}")

        if inserted > 0:
            log_message(cursor, fk_task_run, "INFO", f"Metadata extraction completed. Inserted {inserted} documents.")
            return True
        else:
            log_message(cursor, fk_task_run, "INFO", "No new documents found or all documents already exist")
            return True
            
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Metadata extraction failed: {str(e)}")
        return False

def download_pdfs_step(driver, cursor, fk_task_run, conn, case_event_id):
    """Step 2: Download PDF files for documents with rel_path = 'pending'"""
    
    log_message(cursor, fk_task_run, "INFO", "=== STEP 2: DOWNLOADING PDF FILES ===")
    
    try:
        # Query for pending documents
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
        """, (case_event_id,))
        
        rows = cursor.fetchall()
        if not rows:
            log_message(cursor, fk_task_run, "INFO", "No pending documents to download")
            return True
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(rows)} pending documents to download")
        
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
            dest_path = os.path.join(case_dir, filename)

            # Check if PDF already exists and is valid
            if os.path.exists(dest_path):
                file_size = os.path.getsize(dest_path)
                if file_size > 1024:  # File is valid
                    log_message(cursor, fk_task_run, "INFO", f"PDF already exists and is valid: {filename} ({file_size} bytes) - skipping download")
                    
                    # Update database to reflect existing file
                    rel_path = f"cases\\{fk_case}\\{filename}"
                    cursor.execute("""
                        UPDATE docketwatch.dbo.documents
                        SET rel_path = ?, date_downloaded = GETDATE()
                        WHERE doc_uid = ?
                    """, (rel_path, doc_uid))
                    conn.commit()
                    successful_downloads += 1
                    continue
                else:
                    # File exists but is too small - remove it and re-download
                    log_message(cursor, fk_task_run, "WARNING", f"Existing PDF file too small ({file_size} bytes) - removing and re-downloading")
                    os.remove(dest_path)

            log_message(cursor, fk_task_run, "INFO", 
                f"Processing document {i}/{len(rows)}: {pdf_type} - {pdf_title[:50]}{'...' if len(pdf_title) > 50 else ''}")
            log_message(cursor, fk_task_run, "INFO", f"Document ID: {doc_id}, Case: {fk_case}, Filename: {filename}")

            try:
                log_message(cursor, fk_task_run, "INFO", f"Downloading PDF from: {pdf_url}")
                
                # Navigate to PDF URL
                driver.get(pdf_url)
                time.sleep(3)
                
                # Handle CSRF form if present
                if "referrer_form" in driver.page_source:
                    try:
                        form = driver.find_element(By.ID, "referrer_form")
                        form.submit()
                        log_message(cursor, fk_task_run, "INFO", "CSRF form submitted")
                        time.sleep(3)
                    except:
                        pass
                
                # Check for PACER billing confirmation page
                if "View Document" in driver.page_source and "PACER Service Center" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "PACER billing confirmation page detected - clicking View Document")
                    
                    try:
                        time.sleep(2)
                        selectors = [
                            "//input[@value='View Document']",
                            "//input[@type='submit' and @value='View Document']",
                            "//input[contains(@value, 'View Document')]"
                        ]
                        
                        view_doc_button = None
                        for selector in selectors:
                            try:
                                view_doc_button = driver.find_element(By.XPATH, selector)
                                if view_doc_button:
                                    break
                            except:
                                continue
                        
                        if view_doc_button:
                            driver.execute_script("arguments[0].scrollIntoView(true);", view_doc_button)
                            time.sleep(1)
                            view_doc_button.click()
                            log_message(cursor, fk_task_run, "INFO", "View Document button clicked")
                            time.sleep(5)
                        else:
                            log_message(cursor, fk_task_run, "WARNING", "View Document button not found")
                    
                    except Exception as e:
                        log_message(cursor, fk_task_run, "WARNING", f"Error clicking View Document: {str(e)}")
                
                # Wait for file to download
                time.sleep(8)
                
                # Check if file was downloaded
                if os.path.exists(dest_path):
                    file_size = os.path.getsize(dest_path)
                    if file_size > 1024:  # File should be at least 1KB
                        # Update database
                        rel_path = f"cases\\{fk_case}\\{filename}"
                        cursor.execute("""
                            UPDATE docketwatch.dbo.documents
                            SET rel_path = ?, date_downloaded = GETDATE()
                            WHERE doc_uid = ?
                        """, (rel_path, doc_uid))
                        conn.commit()
                        
                        successful_downloads += 1
                        log_message(cursor, fk_task_run, "INFO", f"Successfully downloaded: {filename} ({file_size} bytes)")
                    else:
                        failed_downloads += 1
                        log_message(cursor, fk_task_run, "WARNING", f"Downloaded file too small: {filename} ({file_size} bytes)")
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                else:
                    failed_downloads += 1
                    log_message(cursor, fk_task_run, "WARNING", f"File not found after download: {filename}")
                
            except Exception as e:
                failed_downloads += 1
                log_message(cursor, fk_task_run, "ERROR", f"Error processing document {doc_id}: {str(e)}")
        
        log_message(cursor, fk_task_run, "INFO", f"Download process completed. Success: {successful_downloads}, Failed: {failed_downloads}")
        return successful_downloads > 0 or failed_downloads == 0
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"PDF download step failed: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Combined PACER PDF processor: metadata + download")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    # Initialize variables for cleanup
    conn = None
    cursor = None
    driver = None
    temp_user_data_dir = None

    try:
        # Database connection
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        log_message(cursor, fk_task_run, "INFO", f"🚀 COMBINED PACER PDF PROCESSOR STARTING")
        log_message(cursor, fk_task_run, "INFO", f"Processing case_event_id: {args.case_event_id}")

        # Get PACER credentials
        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in DB.")
            return
        USERNAME, PASSWORD, LOGIN_URL = row
        log_message(cursor, fk_task_run, "INFO", f"Retrieved PACER credentials for login URL: {LOGIN_URL}")

        # Get case event details
        cursor.execute("""
            SELECT c.id AS case_id,
                c.pacer_id, 
                LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
                e.event_description, 
                e.event_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE e.id = ?
        """, (args.case_event_id,))
        
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", f"No event found for ID {args.case_event_id}")
            return

        case_id, pacer_id, base_url, event_description, event_url = row
        log_message(cursor, fk_task_run, "INFO", f"Event: {event_description}")
        log_message(cursor, fk_task_run, "INFO", f"Event URL: {event_url}")

        # Validate that we have an event URL
        if not event_url or event_url.strip() == "":
            log_message(cursor, fk_task_run, "WARNING", f"No event URL found for case_event_id {args.case_event_id}")
            
            # Check if there are existing pending documents for this case event
            cursor.execute("""
                SELECT COUNT(*) FROM docketwatch.dbo.documents 
                WHERE fk_case_event = ? AND rel_path = 'pending'
            """, (args.case_event_id,))
            pending_count = cursor.fetchone()[0]
            
            if pending_count > 0:
                log_message(cursor, fk_task_run, "INFO", f"Found {pending_count} existing pending documents - skipping metadata extraction, proceeding to download")
                # Skip metadata extraction, go straight to download step
                if not download_pdfs_step(driver, cursor, fk_task_run, conn, args.case_event_id):
                    log_message(cursor, fk_task_run, "WARNING", "PDF download step had issues")
                else:
                    log_message(cursor, fk_task_run, "INFO", "🎉 COMBINED PACER PDF PROCESSOR COMPLETED SUCCESSFULLY")
                return
            else:
                log_message(cursor, fk_task_run, "ERROR", "No event URL and no existing pending documents - cannot proceed")
                return

        # Validate that the URL contains doc1 (indicates it's a document URL)
        if "/doc1/" not in event_url:
            log_message(cursor, fk_task_run, "WARNING", f"Event URL does not contain '/doc1/' - may not be a document URL: {event_url}")
            log_message(cursor, fk_task_run, "WARNING", "Proceeding anyway, but may not find any documents to download")

        # Setup Chrome WebDriver
        log_message(cursor, fk_task_run, "INFO", "Initializing Chrome WebDriver")
        
        # Create unique user data directory to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        temp_user_data_dir = os.path.join(tempfile.gettempdir(), f"chrome_user_data_{unique_id}")
        
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-plugins")
        opts.add_argument("--disable-images")
        opts.add_argument(f"--user-data-dir={temp_user_data_dir}")
        
        # Download preferences
        prefs = {
            "download.default_directory": FINAL_PDF_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1
        }
        opts.add_experimental_option("prefs", prefs)
        
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        log_message(cursor, fk_task_run, "INFO", f"Chrome WebDriver initialized with profile: {temp_user_data_dir}")

        # Login to PACER
        if not login_to_pacer(driver, USERNAME, PASSWORD, LOGIN_URL, cursor, fk_task_run):
            log_message(cursor, fk_task_run, "ERROR", "PACER login failed - aborting")
            return

        # STEP 1: Extract metadata
        if not extract_metadata_step(driver, cursor, fk_task_run, args.case_event_id, case_id, event_url, event_description, base_url):
            log_message(cursor, fk_task_run, "ERROR", "Metadata extraction failed - aborting")
            return
        
        # Commit metadata changes
        conn.commit()

        # STEP 2: Download PDFs
        if not download_pdfs_step(driver, cursor, fk_task_run, conn, args.case_event_id):
            log_message(cursor, fk_task_run, "WARNING", "PDF download step had issues")
        
        log_message(cursor, fk_task_run, "INFO", "🎉 COMBINED PACER PDF PROCESSOR COMPLETED SUCCESSFULLY")

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Critical error: {str(e)}")
        traceback.print_exc()
        if conn:
            conn.rollback()
    
    finally:
        # Cleanup
        if driver:
            try:
                driver.quit()
                log_message(cursor, fk_task_run, "INFO", "Chrome WebDriver closed")
            except:
                pass
        
        if temp_user_data_dir and os.path.exists(temp_user_data_dir):
            try:
                import shutil
                shutil.rmtree(temp_user_data_dir)
                log_message(cursor, fk_task_run, "INFO", "Temporary Chrome profile cleaned up")
            except:
                pass
        
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    main()