"""
PACER PDF Metadata Extraction Script

PURPOSE:
This script extracts PDF document metadata from PACER (Public Access to Court Electronic Records) 
court filing pages and inserts that metadata into the database for later PDF downloading.

WORKFLOW:
1. Updates existing case_events records with de_seq_num values from URLs
2. Retrieves PACER login credentials from the tools table
3. Logs into PACER using Selenium WebDriver
4. Navigates to the specific case event page
5. Handles PACER's CSRF referrer form if present
6. Parses the HTML to extract document links (main dockets and attachments)
7. Inserts document metadata into the documents table

INPUT:
- case_event_id (GUID): ID of the specific case event to process

OUTPUT:
- Inserts records into docketwatch.dbo.documents table with:
  - Document ID, URL, title, type (Docket/Attachment)
  - Sequence number and file path (initially "pending")
  - Links to parent case and event

DOCUMENT DETECTION:
- Primary: Looks for table rows containing 'doc1' URLs and 'document_' identifiers
- Fallback: Extracts document ID directly from the event URL if no table found
- First document = "Docket" type, subsequent = "Attachment" type

ERROR HANDLING:
- Comprehensive logging via scraper_base module
- Database transaction management
- Proper cleanup of WebDriver and database connections

DEPENDENCIES:
- Selenium WebDriver (Chrome)
- BeautifulSoup for HTML parsing
- scraper_base module for logging utilities
- Database: SQL Server via pyodbc
"""

import sys, argparse, pyodbc, os, time, traceback, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from scraper_base import log_message, setup_logging, get_db_cursor, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

def extract_doc_rows(soup):
    return [tr for tr in soup.find_all("tr") if tr.find("a", href=re.compile("doc1")) and 'document_' in str(tr)]

def parse_doc_row(tr, base_url, pdf_type, default_pdf_title):
    tds = tr.find_all("td")
    try:
        a_tag = tr.find("a", href=re.compile(r'doc1'))
        if not a_tag:
            return None

        pdf_url = a_tag['href']
        if not pdf_url.startswith("http"):
            pdf_url = base_url + pdf_url

        match = re.search(r'/doc1/(\d+)', pdf_url)
        doc_id = match.group(1) if match else None  # Return as string, not int

        pdf_no = int(a_tag.text.strip()) if a_tag.text.strip().isdigit() else 0
        desc = default_pdf_title if pdf_type == "Docket" else " ".join(td.get_text(strip=True) for td in tds[2:4])
        filename = f"E{doc_id}.pdf" if doc_id else ""

        return {
            "doc_id": doc_id,
            "pdf_url": pdf_url,
            "pdf_title": desc,
            "pdf_type": pdf_type,
            "pdf_no": pdf_no,
            "rel_path": "pending"
        }
    except:
        return None

def main():
    parser = argparse.ArgumentParser(description="Scrape and insert PACER PDF metadata into documents table.")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    args = parser.parse_args()

    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")

    try:
        conn, cursor = get_db_cursor()
        context = get_task_context_by_tool_id(cursor, 2)
        fk_task_run = context["fk_task_run"] if context else None

        log_message(cursor, fk_task_run, "INFO", f"Starting metadata extraction for case_event_id: {args.case_event_id}")

        log_message(cursor, fk_task_run, "INFO", "Updating case_events with de_seq_num values from URLs")
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET arr_de_seq_nums = 
                SUBSTRING(event_url, CHARINDEX('de_seq_num=', event_url) + 11, 
                        CHARINDEX('&', event_url + '&', CHARINDEX('de_seq_num=', event_url)) 
                        - CHARINDEX('de_seq_num=', event_url) - 11)
            WHERE event_url IS NOT NULL
              AND arr_de_seq_nums IS NULL
              AND event_url LIKE '%de_seq_num%'
        """)
        updated_rows = cursor.rowcount
        conn.commit()
        log_message(cursor, fk_task_run, "INFO", f"Updated {updated_rows} case_events records with de_seq_num values")

        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in DB.")
            sys.exit()
        USERNAME, PASSWORD, LOGIN_URL = row
        log_message(cursor, fk_task_run, "INFO", f"Retrieved PACER credentials for login URL: {LOGIN_URL}")

        cursor.execute("""
            SELECT 
                c.id,
                LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
                e.event_description,
                e.event_url,
                ps.url AS pacer_site_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
            WHERE e.id = ?
        """, (args.case_event_id,))

        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "INFO", f"No event found for ID {args.case_event_id}")
            sys.exit()

        case_id, base_url, event_description, event_url, pacer_site_url = row
        log_message(cursor, fk_task_run, "INFO", f"Processing case {case_id}, event: {event_description[:100]}{'...' if len(event_description) > 100 else ''}")
        log_message(cursor, fk_task_run, "INFO", f"Event URL: {event_url}")
        log_message(cursor, fk_task_run, "INFO", f"PACER site URL: {pacer_site_url}")

        log_message(cursor, fk_task_run, "INFO", "Initializing Chrome WebDriver for PACER login")
        opts = Options()
        opts.add_argument("--headless=new")  # Commented out for debugging
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        wait = WebDriverWait(driver, 15)

        # Login
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

        # Load the event page
        log_message(cursor, fk_task_run, "INFO", f"Navigating to event page: {event_url}")
        driver.get(event_url)
        time.sleep(2)

        # Handle PACER warning page for already purchased documents
        if "The link to this page may not have originated from within CM/ECF" in driver.page_source:
            log_message(cursor, fk_task_run, "INFO", "Detected PACER warning page for already purchased document")
            try:
                continue_link = driver.find_element(By.LINK_TEXT, "Continue")
                continue_link.click()
                time.sleep(3)
                log_message(cursor, fk_task_run, "INFO", "Clicked 'Continue' link to proceed to document page")
                log_message(cursor, fk_task_run, "INFO", f"Current URL after Continue: {driver.current_url}")
                
                # Debug: Log what page we're on now
                if "Transaction Receipt" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "Now on Transaction Receipt page")
                elif "View Document" in driver.page_source:
                    log_message(cursor, fk_task_run, "INFO", "Found View Document on current page")
                else:
                    log_message(cursor, fk_task_run, "WARNING", "Not on expected page after Continue click")
                    log_message(cursor, fk_task_run, "DEBUG", f"Page title: {driver.title}")
                    
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Failed to click Continue link: {str(e)}")
        
        if "referrer_form" in driver.page_source:
            try:
                driver.find_element(By.ID, "referrer_form").submit()
                time.sleep(3)
                log_message(cursor, fk_task_run, "INFO", "PACER CSRF form submitted.")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Referrer form submission failed: {str(e)}")
        else:
            log_message(cursor, fk_task_run, "INFO", "No CSRF referrer form found - proceeding")

        log_message(cursor, fk_task_run, "INFO", "Parsing HTML to extract document links")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        inserted = 0  # Initialize inserted counter
        
        # Add detailed logging of the page content to debug detection issues
        page_text = driver.page_source.lower()
        log_message(cursor, fk_task_run, "DEBUG", f"Page contains 'transaction receipt': {'transaction receipt' in page_text}")
        log_message(cursor, fk_task_run, "DEBUG", f"Page contains 'view document': {'view document' in page_text}")
        log_message(cursor, fk_task_run, "DEBUG", f"Page contains 'continue': {'continue' in page_text}")
        log_message(cursor, fk_task_run, "DEBUG", f"Page contains 'iframe': {'iframe' in page_text}")
        log_message(cursor, fk_task_run, "DEBUG", f"Page contains 'show_temp.pl': {'show_temp.pl' in page_text}")
        log_message(cursor, fk_task_run, "DEBUG", f"Page title: {driver.title}")
        
        # Look for the warning message about already purchased documents
        warning_patterns = [
            "document has been purchased by this account",
            "you have already purchased this document",
            "already purchased",
            "previously purchased"
        ]
        has_warning = any(pattern in page_text for pattern in warning_patterns)
        log_message(cursor, fk_task_run, "DEBUG", f"Has purchase warning: {has_warning}")
        
        # Check if we're on a transaction receipt page (already purchased document)
        if "Transaction Receipt" in driver.page_source or "View Document" in driver.page_source or has_warning:
            log_message(cursor, fk_task_run, "INFO", "Detected transaction receipt page - looking for View Document button")
            log_message(cursor, fk_task_run, "DEBUG", f"Page title: {driver.title}")
            log_message(cursor, fk_task_run, "DEBUG", f"Current URL: {driver.current_url}")
            
            # Look for View Document form or button
            view_doc_button = soup.find("input", {"type": "submit", "value": "View Document"})
            if view_doc_button:
                log_message(cursor, fk_task_run, "INFO", "Found View Document button - clicking to access PDF")
                
                # Click the View Document button to navigate to the PDF
                try:
                    # Find the button element in the driver and click it
                    button_element = driver.find_element(By.XPATH, "//input[@type='submit'][@value='View Document']")
                    button_element.click()
                    time.sleep(3)  # Wait for navigation
                    
                    log_message(cursor, fk_task_run, "INFO", f"Clicked View Document button, now on: {driver.current_url}")
                    
                    # Re-parse the new page
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    
                    # Check if we're now on a PDF viewer page with iframe
                    if "iframe" in driver.page_source.lower():
                        log_message(cursor, fk_task_run, "INFO", "After View Document click: detected PDF viewer page with iframe")
                        iframe = soup.find("iframe")
                        if iframe and iframe.get("src"):
                            pdf_src = iframe.get("src")
                            if not pdf_src.startswith("http"):
                                pdf_src = base_url + pdf_src
                            
                            log_message(cursor, fk_task_run, "INFO", f"Found direct PDF URL in iframe: {pdf_src}")
                            
                            # Extract doc_id from the current URL
                            match = re.search(r'/doc1/(\d+)', driver.current_url)
                            if match:
                                doc_id = match.group(1)
                                log_message(cursor, fk_task_run, "INFO", f"Extracted doc_id {doc_id} from current URL")
                                
                                # Check if document already exists
                                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_id,))
                                if cursor.fetchone()[0] == 0:
                                    # For already-purchased documents, store the original document URL 
                                    # (not the temporary show_temp.pl URL) so it can be accessed again
                                    # The PDF download script will need to handle the transaction receipt workflow
                                    original_doc_url = driver.current_url  # This is the stable doc1/XXXXX URL
                                    cursor.execute("""
                                        INSERT INTO docketwatch.dbo.documents (
                                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                                        )
                                        VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'purchased_pending', GETDATE())
                                    """, (case_id, args.case_event_id, 2, doc_id, original_doc_url, event_description))
                                    conn.commit()
                                    log_message(cursor, fk_task_run, "INFO", f"Inserted purchased document {doc_id} with original document URL (not temp PDF URL)")
                                    inserted = 1
                                else:
                                    log_message(cursor, fk_task_run, "INFO", f"Document {doc_id} already exists in database")
                            else:
                                log_message(cursor, fk_task_run, "WARNING", "Could not extract doc_id from current URL after View Document click")
                        else:
                            log_message(cursor, fk_task_run, "WARNING", "No iframe src found after View Document click")
                    else:
                        log_message(cursor, fk_task_run, "WARNING", "No iframe detected after clicking View Document button")
                        
                except Exception as e:
                    log_message(cursor, fk_task_run, "ERROR", f"Error clicking View Document button: {str(e)}")
            else:
                log_message(cursor, fk_task_run, "WARNING", "No View Document button found on transaction receipt page")
                # Let's see what buttons/forms are available
                all_inputs = soup.find_all("input", {"type": "submit"})
                log_message(cursor, fk_task_run, "DEBUG", f"Found submit buttons: {[inp.get('value', 'No value') for inp in all_inputs]}")
                all_forms = soup.find_all("form")
                log_message(cursor, fk_task_run, "DEBUG", f"Found {len(all_forms)} forms on page")
        
        # Check if there's a "Continue" button instead (different already purchased flow)
        elif "Continue" in driver.page_source and ("already" in page_text or "purchased" in page_text):
            log_message(cursor, fk_task_run, "INFO", "Detected 'Continue' button on already purchased document page")
            
            # Look for Continue button and click it
            try:
                continue_button = driver.find_element(By.XPATH, "//input[@type='submit'][@value='Continue']")
                if continue_button:
                    log_message(cursor, fk_task_run, "INFO", "Clicking Continue button")
                    continue_button.click()
                    time.sleep(3)
                    
                    # Now check if we're on the PDF viewer page
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    if "iframe" in driver.page_source.lower():
                        log_message(cursor, fk_task_run, "INFO", "After Continue: detected PDF viewer page with iframe")
                        iframe = soup.find("iframe")
                        if iframe and iframe.get("src"):
                            pdf_src = iframe.get("src")
                            if not pdf_src.startswith("http"):
                                pdf_src = base_url + pdf_src
                            
                            log_message(cursor, fk_task_run, "INFO", f"Found direct PDF URL in iframe: {pdf_src}")
                            
                            # Try to extract doc_id from the original event URL
                            match = re.search(r'/doc1/(\d+)', event_url)
                            if match:
                                doc_id = match.group(1)
                                log_message(cursor, fk_task_run, "INFO", f"Extracted doc_id {doc_id} from original event URL")
                                
                                # Check if document already exists
                                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_id,))
                                if cursor.fetchone()[0] == 0:
                                    # For already-purchased documents, store the original event URL 
                                    # (not the temporary show_temp.pl URL) so it can be accessed again
                                    original_doc_url = event_url  # This is the stable doc1/XXXXX URL
                                    cursor.execute("""
                                        INSERT INTO docketwatch.dbo.documents (
                                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                                        )
                                        VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'purchased_pending', GETDATE())
                                    """, (case_id, args.case_event_id, 2, doc_id, original_doc_url, event_description))
                                    conn.commit()
                                    log_message(cursor, fk_task_run, "INFO", f"Inserted purchased document {doc_id} with original document URL (not temp PDF URL)")
                                    inserted = 1
                                else:
                                    log_message(cursor, fk_task_run, "INFO", f"Document {doc_id} already exists in database")
                            else:
                                log_message(cursor, fk_task_run, "WARNING", "Could not extract doc_id from event URL")
                        else:
                            log_message(cursor, fk_task_run, "WARNING", "No iframe src found after Continue")
                    else:
                        log_message(cursor, fk_task_run, "WARNING", "No iframe detected after clicking Continue")
                else:
                    log_message(cursor, fk_task_run, "WARNING", "Continue button not found despite text detection")
            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Error clicking Continue button: {str(e)}")
        
        # Check if we're already on a PDF viewer page (with iframe)
        elif "show_temp.pl" in driver.page_source and "iframe" in driver.page_source:
            log_message(cursor, fk_task_run, "INFO", "Detected PDF viewer page with iframe - extracting direct PDF URL")
            
            # Look for iframe with PDF source
            iframe = soup.find("iframe")
            if iframe and iframe.get("src"):
                pdf_src = iframe.get("src")
                if not pdf_src.startswith("http"):
                    pdf_src = base_url + pdf_src
                
                log_message(cursor, fk_task_run, "INFO", f"Found direct PDF URL in iframe: {pdf_src}")
                
                # Try to extract doc_id from the current URL (not the iframe src)
                match = re.search(r'/doc1/(\d+)', driver.current_url)
                if match:
                    doc_id = match.group(1)
                    log_message(cursor, fk_task_run, "INFO", f"Extracted doc_id {doc_id} from current URL")
                    
                    # Check if document already exists
                    cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_id,))
                    if cursor.fetchone()[0] == 0:
                        # For already-purchased documents, store the original document URL 
                        # (not the temporary show_temp.pl URL) so it can be accessed again
                        original_doc_url = driver.current_url  # This is the stable doc1/XXXXX URL
                        cursor.execute("""
                            INSERT INTO docketwatch.dbo.documents (
                                fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                                pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                            )
                            VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'purchased_pending', GETDATE())
                        """, (case_id, args.case_event_id, 2, doc_id, original_doc_url, event_description))
                        conn.commit()
                        log_message(cursor, fk_task_run, "INFO", f"Inserted purchased document {doc_id} with original document URL (not temp PDF URL)")
                        inserted = 1
                    else:
                        log_message(cursor, fk_task_run, "INFO", f"Document {doc_id} already exists in database")
                    
                    # Don't exit early - let user see the browser
                    log_message(cursor, fk_task_run, "INFO", f"Metadata extraction completed. Inserted {inserted} new documents.")
                    log_message(cursor, fk_task_run, "INFO", "Browser left open for inspection. Close manually when done.")
                    return
                else:
                    log_message(cursor, fk_task_run, "WARNING", "Could not extract doc_id from current URL")
            else:
                log_message(cursor, fk_task_run, "WARNING", "PDF viewer page detected but no iframe found")
        
        # Continue with normal document row parsing if not on transaction receipt page
        doc_rows = extract_doc_rows(soup)
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(doc_rows)} document rows in page")

        if not doc_rows:
            log_message(cursor, fk_task_run, "INFO", "No document table found - attempting fallback extraction")
            match = re.search(r'/doc1/(\d+)', event_url)
            if match:
                doc_id = match.group(1)  # Keep as string for varchar column
                log_message(cursor, fk_task_run, "INFO", f"Extracted doc_id {doc_id} from event URL")
                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_id,))
                if cursor.fetchone()[0] == 0:
                    # NOTE: doc_id changed from int to varchar - now passed as string
                    cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'pending', GETDATE())
                    """, (case_id, args.case_event_id, 2, doc_id, event_url, event_description
                    ))
                    conn.commit()
                    log_message(cursor, fk_task_run, "INFO", f"Inserted fallback docket PDF {doc_id}")
                    inserted = 1
                else:
                    log_message(cursor, fk_task_run, "INFO", f"Document {doc_id} already exists in database")
            else:
                log_message(cursor, fk_task_run, "WARNING", "No doc_id found in event URL - no documents to extract")
        else:
            log_message(cursor, fk_task_run, "INFO", f"Processing {len(doc_rows)} document rows")

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

if __name__ == '__main__':
    main()
