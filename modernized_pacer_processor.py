"""
Modernized process_pacer_event_pdf.py
====================================

This is a refactored version of process_pacer_event_pdf.py that uses the new modular components.
This version is designed to run from the main python folder alongside your other scripts.

Key improvements:
- Uses workflow_manager for orchestration
- Cleaner separation of concerns
- Better error handling and logging
- More maintainable code structure
"""

import sys
import argparse
import pyodbc
import os
import time
import traceback
import logging
import zipfile
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Import our new modular components (from same directory)
from workflows.workflow_manager import DocketWatchWorkflow
from core.case_event_manager import log_case_message
from core.pdf_operations import get_pdf_processing_stats

# Legacy imports for compatibility (until fully migrated)
from scraper_base import get_db_cursor, get_task_context_by_tool_id

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"

class PacerEventProcessor:
    """
    Modernized PACER event PDF processor using modular components.
    """
    
    def __init__(self, case_event_id):
        self.case_event_id = case_event_id
        self.conn = None
        self.cursor = None
        self.driver = None
        self.fk_task_run = None
        
        # Setup logging
        script_filename = os.path.splitext(os.path.basename(__file__))[0]
        log_path = f"u:/docketwatch/python/logs/{script_filename}.log"
        logging.basicConfig(filename=log_path, level=logging.INFO,
                           format="%(asctime)s - %(levelname)s - %(message)s")
        
    def __enter__(self):
        """Context manager entry - setup resources."""
        try:
            # Database connection
            self.conn, self.cursor = get_db_cursor()
            
            # Get task context
            context = get_task_context_by_tool_id(self.cursor, 2)
            self.fk_task_run = context["fk_task_run"] if context else None
            
            # Initialize workflow manager
            self.workflow = DocketWatchWorkflow(
                self.cursor, 
                docs_root_dir=FINAL_PDF_DIR,
                fk_task_run=self.fk_task_run
            )
            
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Processing case_event_id: {self.case_event_id}")
            
            return self
            
        except Exception as e:
            logging.error(f"Failed to initialize processor: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        if self.driver:
            self.driver.quit()
        if self.conn:
            self.conn.close()
            
        if exc_type:
            log_case_message(self.cursor, self.fk_task_run, "ERROR", 
                           f"Processor failed: {exc_val}")
    
    def setup_selenium(self):
        """Setup Chrome WebDriver for PACER interaction."""
        opts = Options()
        # headless opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        
        prefs = {
            "download.default_directory": FINAL_PDF_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1
        }
        opts.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        return WebDriverWait(self.driver, 15)
    
    def discover_missing_event_url(self, event_info):
        """
        Discover and populate missing event_url by scraping PACER docket page.
        This handles cases where event_url is NULL but we have basic event info.
        """
        try:
            # Get additional event details for URL construction
            self.cursor.execute("""
                SELECT e.event_no, e.event_date, e.fk_cases, c.pacer_id, ps.url as pacer_site_url
                FROM docketwatch.dbo.case_events e
                INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
                INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
                WHERE e.id = ?
            """, (self.case_event_id,))
            
            row = self.cursor.fetchone()
            if not row:
                raise ValueError(f"Could not get event details for {self.case_event_id}")
            
            event_no, event_date, fk_cases, pacer_id, pacer_site_url = row
            
            if not event_no or not pacer_id:
                raise ValueError(f"Missing event_no ({event_no}) or pacer_id ({pacer_id}) - cannot discover URL")
            
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Attempting to discover event_url for event_no {event_no} in case {pacer_id}")
            
            # Construct docket report URL to find the event
            docket_url = f"{pacer_site_url}/cgi-bin/DktRpt.pl?{pacer_id}"
            
            self.driver.get(docket_url)
            time.sleep(3)
            
            # Handle CSRF form if present
            if "referrer_form" in self.driver.page_source:
                try:
                    self.driver.find_element(By.ID, "referrer_form").submit()
                    time.sleep(3)
                    log_case_message(self.cursor, self.fk_task_run, "INFO", "PACER CSRF form submitted during URL discovery")
                except Exception as e:
                    log_case_message(self.cursor, self.fk_task_run, "WARNING", f"CSRF form submission failed: {str(e)}")
            
            # Parse the docket page to find the event
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
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
                self.cursor.execute("""
                    UPDATE docketwatch.dbo.case_events
                    SET event_url = ?
                    WHERE id = ?
                """, (event_url_found, self.case_event_id))
                self.conn.commit()
                
                log_case_message(self.cursor, self.fk_task_run, "INFO", 
                               f"Discovered and updated event_url: {event_url_found}")
                
                # Update our event_info with the discovered URL
                event_info['event_url'] = event_url_found
                event_info['base_url'] = event_url_found.split('.gov')[0] + '.gov' if '.gov' in event_url_found else pacer_site_url
                
                return event_url_found
            else:
                log_case_message(self.cursor, self.fk_task_run, "WARNING", 
                               f"Could not find document link for event_no {event_no} on docket page")
                return None
                
        except Exception as e:
            log_case_message(self.cursor, self.fk_task_run, "ERROR", 
                           f"Failed to discover event_url: {str(e)}")
            return None

    def get_event_info(self):
        """Get case event information from database."""
        self.cursor.execute("""
            SELECT c.id AS case_id,
                c.pacer_id, 
                LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
                e.event_description, e.event_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            WHERE e.id = ?
        """, (self.case_event_id,))
        
        row = self.cursor.fetchone()
        if not row:
            raise ValueError(f"No event found for ID {self.case_event_id}")
        
        event_info = {
            'case_id': row.case_id,
            'pacer_id': row.pacer_id,
            'base_url': row.base_url,
            'event_description': row.event_description,
            'event_url': row.event_url
        }
        
        # Check if event_url is missing and try to discover it
        if not row.event_url:
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Event {self.case_event_id} has no event_url - attempting to discover")
            
            # Setup selenium for URL discovery
            if not self.driver:
                self.setup_selenium()
                # Login to PACER for URL discovery
                self.login_to_pacer(WebDriverWait(self.driver, 15))
            
            # Try to discover the missing URL
            discovered_url = self.discover_missing_event_url(event_info)
            
            if not discovered_url:
                raise ValueError(f"Event {self.case_event_id} has no event_url and could not discover one - cannot process")
        
        # Validate that we now have a valid event_url
        event_url = str(event_info['event_url']).strip() if event_info['event_url'] else ''
        if not event_url:
            raise ValueError(f"Event {self.case_event_id} has empty event_url - cannot process")
        
        # Basic URL validation - must contain expected PACER patterns
        if not any(pattern in event_url.lower() for pattern in ['.uscourts.gov', 'pacer']):
            raise ValueError(f"Event {self.case_event_id} has invalid event_url: {event_url}")
        
        logging.info(f"Processing event {self.case_event_id} with URL: {event_url}")
        
        return event_info
    
    def login_to_pacer(self, wait):
        """Login to PACER using stored credentials."""
        self.cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = self.cursor.fetchone()
        if not row:
            raise ValueError("PACER credentials not found in DB")
        
        USERNAME, PASSWORD, LOGIN_URL = row
        
        self.driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.NAME, "loginForm:loginName"))).send_keys(USERNAME)
        self.driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
        
        try:
            self.driver.find_element(By.NAME, "loginForm:clientCode").send_keys("DocketWatch")
        except:
            pass
            
        self.driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        time.sleep(3)
        
        log_case_message(self.cursor, self.fk_task_run, "INFO", "PACER login completed")
    
    def process_pacer_documents(self, event_info):
        """Process PACER documents for the event - includes discovery, insertion, and downloading."""
        # Navigate to the event page
        self.driver.get(event_info['event_url'])
        time.sleep(2)

        # Handle CSRF form if present
        if "referrer_form" in self.driver.page_source:
            try:
                self.driver.find_element(By.ID, "referrer_form").submit()
                time.sleep(3)
                log_case_message(self.cursor, self.fk_task_run, "INFO", "PACER CSRF form submitted")
            except Exception as e:
                log_case_message(self.cursor, self.fk_task_run, "ERROR", 
                               f"Referrer form submission failed: {str(e)}")

        # Extract and insert document metadata
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        doc_rows = self.extract_doc_rows(soup)
        inserted = 0

        if not doc_rows:
            # Fallback: extract doc_id from URL
            import re
            match = re.search(r'/doc1/(\d+)', event_info['event_url'])
            if match:
                doc_id = str(match.group(1))  # Convert to string for varchar schema
                self.cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_id,))
                if self.cursor.fetchone()[0] == 0:
                    # INSERT into documents table - doc_id is varchar, isfound defaults to NULL
                    self.cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, 'Docket', 0, 'pending', GETDATE())
                    """, (
                        event_info['case_id'], self.case_event_id, 2, doc_id, 
                        event_info['event_url'], event_info['event_description']
                    ))
                    self.conn.commit()
                    log_case_message(self.cursor, self.fk_task_run, "INFO", f"Inserted fallback docket PDF {doc_id}")
        else:
            # Process document rows found on page
            for i, tr in enumerate(doc_rows):
                pdf_type = "Docket" if i == 0 else "Attachment"
                doc_data = self.parse_doc_row(tr, event_info['base_url'], pdf_type, event_info['event_description'])
                if not doc_data or not doc_data["doc_id"]:
                    continue
                    
                self.cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE doc_id = ?", (doc_data["doc_id"],))
                if self.cursor.fetchone()[0] == 0:
                    # INSERT into documents table - doc_id is varchar, isfound defaults to NULL
                    self.cursor.execute("""
                        INSERT INTO docketwatch.dbo.documents (
                            fk_case, fk_case_event, fk_tool, doc_id, pdf_url,
                            pdf_title, pdf_type, pdf_no, rel_path, date_downloaded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
                    """, (
                        event_info['case_id'], self.case_event_id, 2,
                        doc_data["doc_id"], doc_data["pdf_url"],
                        doc_data["pdf_title"], doc_data["pdf_type"],
                        doc_data["pdf_no"], doc_data["rel_path"]
                    ))
                    inserted += 1
            self.conn.commit()
            log_case_message(self.cursor, self.fk_task_run, "INFO", f"Inserted metadata for {inserted} documents")

        # Now download the actual PDFs
        self.download_pending_pdfs()
        
        return True

    def extract_doc_rows(self, soup):
        """Extract document rows from PACER page HTML."""
        import re
        return [tr for tr in soup.find_all("tr") if tr.find("a", href=re.compile("doc1")) and 'document_' in str(tr)]

    def parse_doc_row(self, tr, base_url, pdf_type, default_pdf_title):
        """Parse individual document row to extract metadata."""
        import re
        tds = tr.find_all("td")
        try:
            a_tag = tr.find("a", href=re.compile(r'doc1'))
            if not a_tag:
                return None

            pdf_url = a_tag['href']
            if not pdf_url.startswith("http"):
                pdf_url = base_url + pdf_url

            match = re.search(r'/doc1/(\d+)', pdf_url)
            doc_id = str(match.group(1)) if match else None  # Convert to string for varchar schema

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
        except:
            return None

    def download_pending_pdfs(self):
        """Download PDFs for documents with rel_path = 'pending'."""
        import zipfile
        import re
        
        # Query for pending documents using the complex download URL logic from original
        self.cursor.execute("""
            SELECT 
                c.pacer_id AS case_id,
                c.id AS fk_case,
                LEFT(e.event_url, CHARINDEX('.gov', e.event_url) + 3) AS base_url,
                e.event_description,
                e.event_url,
                e.arr_de_seq_nums,
                p.doc_uid,
                ps.url,
                p.doc_id,
                RIGHT(CAST(p.doc_id AS VARCHAR), 8) AS doc_id_str,
                p.pdf_type,
                ps.url + '/cgi-bin/show_multidocs.pl?caseid=' + 
                CAST(c.pacer_id AS VARCHAR) +
                '&arr_de_seq_nums=' + 
                CAST(e.arr_de_seq_nums AS VARCHAR) +
                '&pdf_header=2&pdf_toggle_possible=1' +
                CASE 
                    WHEN EXISTS (
                        SELECT 1 
                        FROM docketwatch.dbo.documents p2 
                        WHERE p2.fk_case_event = e.id 
                        AND p2.doc_id <> p.doc_id
                    )
                    THEN '&exclude_attachments=' + ISNULL((
                        STUFF((
                            SELECT ',' + RIGHT(CAST(p2.doc_id AS VARCHAR), 8)
                            FROM docketwatch.dbo.documents p2
                            WHERE p2.fk_case_event = e.id 
                            AND p2.doc_id <> p.doc_id
                            FOR XML PATH(''), TYPE
                        ).value('.', 'NVARCHAR(MAX)'), 1, 1, '')
                    ), '')
                    ELSE ''
                END +
                '&zipit=1' AS download_url
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON c.id = e.fk_cases
            INNER JOIN docketwatch.dbo.pacer_sites ps ON ps.id = c.fk_pacer_site
            INNER JOIN docketwatch.dbo.documents p ON p.fk_case_event = e.id
            WHERE e.id = ? AND p.rel_path = 'pending'
        """, (self.case_event_id,))
        
        rows = self.cursor.fetchall()
        
        for row in rows:
            doc_id = row.doc_id
            doc_uid = row.doc_uid
            fk_case = row.fk_case
            download_url = row.download_url
            filename = f"E{doc_id}.pdf"
            case_dir = os.path.join(FINAL_PDF_DIR, str(fk_case))
            os.makedirs(case_dir, exist_ok=True)
            dest_path = os.path.join(case_dir, filename)

            try:
                log_case_message(self.cursor, self.fk_task_run, "INFO", f"Download URL for doc_id {doc_id}: {download_url}")
                self.driver.get(download_url)
                time.sleep(8)

                # Handle CSRF referrer form if present
                if "Warning:" in self.driver.page_source and "referrer_form" in self.driver.page_source:
                    try:
                        form = self.driver.find_element(By.ID, "referrer_form")
                        self.driver.execute_script("arguments[0].submit();", form)
                        time.sleep(3)
                        log_case_message(self.cursor, self.fk_task_run, "INFO", "Submitted CSRF referrer form")
                    except Exception as e:
                        log_case_message(self.cursor, self.fk_task_run, "ERROR", f"CSRF form submission failed: {str(e)}")

                # Click download button
                try:
                    download_button = self.driver.find_element(By.XPATH, "//input[@type='button' and @value='Download Documents']")
                    self.driver.execute_script("arguments[0].click();", download_button)
                    time.sleep(3)
                except:
                    log_case_message(self.cursor, self.fk_task_run, "WARNING", f"Download button not found for {filename}")

                # Wait for ZIP file to download
                zip_file = None
                start_time = time.time()
                while time.time() - start_time < 30:
                    zips = [f for f in os.listdir(FINAL_PDF_DIR) if f.endswith(".zip")]
                    if zips:
                        latest = max([os.path.join(FINAL_PDF_DIR, f) for f in zips], key=os.path.getctime)
                        if not os.path.exists(latest + ".crdownload"):
                            zip_file = latest
                            break
                    time.sleep(1)

                # Extract and process downloaded ZIP
                if zip_file:
                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                        zip_ref.extractall(FINAL_PDF_DIR)
                        for name in zip_ref.namelist():
                            extracted_pdf = os.path.join(FINAL_PDF_DIR, name)
                            if os.path.exists(extracted_pdf):
                                file_size = os.path.getsize(extracted_pdf)
                                if file_size < 2048:
                                    log_case_message(self.cursor, self.fk_task_run, "WARNING", 
                                                   f"Downloaded file too small (<2KB): {filename} ({file_size} bytes)")
                                    os.remove(extracted_pdf)
                                    continue

                                # Move to correct location and update database
                                os.rename(extracted_pdf, dest_path)
                                rel_path = f"cases\\{fk_case}\\{filename}"
                                self.cursor.execute("""
                                    UPDATE docketwatch.dbo.documents
                                    SET rel_path = ?, date_downloaded = GETDATE()
                                    WHERE doc_uid = ?
                                """, (rel_path, doc_uid))
                                self.conn.commit()
                                log_case_message(self.cursor, self.fk_task_run, "INFO", 
                                               f"Downloaded and saved: {filename} ({file_size} bytes)")

                    # Clean up ZIP file
                    os.remove(zip_file)
                else:
                    log_case_message(self.cursor, self.fk_task_run, "WARNING", f"ZIP not found for {filename}")

            except Exception as ex:
                log_case_message(self.cursor, self.fk_task_run, "ERROR", f"Download failed for {filename}: {str(ex)}")
    
    def check_and_process_missing_summaries(self):
        """Check for PDFs without summaries and process them."""
        try:
            # Query for PDFs that don't have summaries - CORRECTED COLUMN NAMES
            self.cursor.execute("""
                SELECT d.doc_uid, d.rel_path, d.total_pages
                FROM docketwatch.dbo.documents d
                WHERE d.fk_case_event = ?
                AND d.rel_path LIKE '%.pdf'
                AND d.isfound = 1
                AND (d.summary_ai IS NULL OR d.summary_ai = '')
                AND d.rel_path IS NOT NULL
                ORDER BY d.doc_uid
            """, (self.case_event_id,))
            
            missing_summaries = self.cursor.fetchall()
            
            if not missing_summaries:
                logging.info(f"No PDFs missing summaries for event {self.case_event_id}")
                return 0
            
            logging.info(f"Found {len(missing_summaries)} PDFs missing summaries for event {self.case_event_id}")
            
            processed_count = 0
            for doc in missing_summaries:
                try:
                    logging.info(f"Processing summary for document {doc.doc_uid}: {doc.rel_path}")
                    
                    # Use the workflow manager to generate summary
                    result = self.workflow.process_pdf_summary(doc.doc_uid)
                    
                    if result and result.get('status') == 'success':
                        logging.info(f"Successfully generated summary for document {doc.doc_uid}")
                        processed_count += 1
                        
                        # Log the success
                        log_case_message(self.cursor, self.fk_task_run, "INFO", 
                                       f"Generated missing summary for {doc.rel_path}")
                    else:
                        logging.warning(f"Failed to generate summary for document {doc.doc_uid}")
                        log_case_message(self.cursor, self.fk_task_run, "WARNING", 
                                       f"Failed to generate summary for {doc.rel_path}")
                        
                except Exception as e:
                    logging.error(f"Error processing summary for document {doc.doc_uid}: {str(e)}")
                    log_case_message(self.cursor, self.fk_task_run, "ERROR", 
                                   f"Summary error for {doc.rel_path}: {str(e)}")
            
            logging.info(f"Processed summaries for {processed_count}/{len(missing_summaries)} documents")
            return processed_count
            
        except Exception as e:
            logging.error(f"Error checking for missing summaries: {str(e)}")
            return 0

    def run_complete_workflow(self):
        """Run the complete processing workflow."""
        try:
            # Get event information and validate URL
            logging.info(f"Starting workflow for case_event_id: {self.case_event_id}")
            event_info = self.get_event_info()
            
            # Log event details for debugging
            logging.info(f"Event details: {event_info['event_description']}")
            logging.info(f"Target URL: {event_info['event_url']}")
            
            # Setup Selenium
            wait = self.setup_selenium()
            
            # Login to PACER
            self.login_to_pacer(wait)
            
            # Process PACER documents (download, metadata extraction)
            self.process_pacer_documents(event_info)
            
            # Use the workflow manager for OCR and summarization
            result = self.workflow.process_case_event_complete(self.case_event_id)
            
            # Check for PDFs missing summaries and process them
            missing_summaries_processed = self.check_and_process_missing_summaries()
            if missing_summaries_processed > 0:
                logging.info(f"Generated {missing_summaries_processed} missing summaries")
            
            # Log final results
            stats = get_pdf_processing_stats(self.cursor, self.case_event_id)
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Processing complete. Final stats: {stats}")
            
            # Add missing summaries info to result
            if isinstance(result, dict):
                result['missing_summaries_processed'] = missing_summaries_processed
            
            return result
            
        except ValueError as e:
            # These are validation errors - don't retry
            logging.error(f"Validation error: {str(e)}")
            log_case_message(self.cursor, self.fk_task_run, "ERROR", 
                           f"Validation failed: {str(e)}")
            raise
            
        except Exception as e:
            log_case_message(self.cursor, self.fk_task_run, "ERROR", 
                           f"Workflow failed: {str(e)}")
            raise

def main():
    """Main entry point - maintains same interface as original script."""
    parser = argparse.ArgumentParser(description="Download PACER PDF for specific case_event")
    parser.add_argument("case_event_id", type=str, help="GUID of the case_events record")
    parser.add_argument('--check-summaries-only', action='store_true', 
                       help='Only check for missing summaries, don\'t download new PDFs')
    parser.add_argument('--batch-summary-check', action='store_true', 
                       help='Check for missing summaries across all events (no processing)')
    args = parser.parse_args()

    try:
        if args.batch_summary_check:
            # Just check for missing summaries across all events
            import pyodbc
            
            # Connect to database
            conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=10.146.176.84;"
                "DATABASE=docketwatch;"
                "UID=docketwatch;"
                "PWD=***;"
                "TrustServerCertificate=yes;"
            )
            cursor = conn.cursor()
            
            result = check_missing_summaries_batch(cursor)
            print(f"Summary check result: {result['message']}")
            
            if result['status'] == 'success' and result.get('events_summary'):
                print("\nEvents with missing summaries:")
                for event_id, docs in result['events_summary'].items():
                    print(f"  Event {event_id}: {len(docs)} PDFs missing summaries")
                    for doc in docs[:3]:  # Show first 3
                        print(f"    - {doc['filename']} ({doc['pages']} pages)")
                    if len(docs) > 3:
                        print(f"    ... and {len(docs) - 3} more")
            
            conn.close()
            return
        
        # Normal processing or summary-only check
        # Use context manager for resource management
        with PacerEventProcessor(args.case_event_id) as processor:
            if args.check_summaries_only:
                # Only check and process missing summaries
                logging.info(f"Checking for missing summaries for event {args.case_event_id}")
                count = processor.check_and_process_missing_summaries()
                print(f"Processed summaries for {count} documents")
            else:
                # Full workflow
                result = processor.run_complete_workflow()
                print(f"Processing completed successfully: {result}")
            
    except Exception as e:
        logging.error(f"Unhandled error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

def check_missing_summaries_batch(cursor, case_event_ids=None, limit=None):
    """
    Standalone function to check for missing summaries across multiple events.
    
    Args:
        cursor: Database cursor
        case_event_ids: List of specific event IDs to check, or None for all
        limit: Maximum number of documents to process, or None for all
    
    Returns:
        Dict with results
    """
    try:
        if case_event_ids:
            # Check specific events - CORRECTED COLUMN NAMES
            placeholders = ','.join(['?' for _ in case_event_ids])
            query = f"""
                SELECT d.fk_case_event, d.doc_uid, d.rel_path, d.total_pages
                FROM docketwatch.dbo.documents d
                WHERE d.fk_case_event IN ({placeholders})
                AND d.rel_path LIKE '%.pdf'
                AND d.isfound = 1
                AND (d.summary_ai IS NULL OR d.summary_ai = '')
                AND d.rel_path IS NOT NULL
                ORDER BY d.fk_case_event, d.doc_uid
            """
            if limit:
                query += f" OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
            cursor.execute(query, case_event_ids)
        else:
            # Check all events - CORRECTED COLUMN NAMES
            query = """
                SELECT d.fk_case_event, d.doc_uid, d.rel_path, d.total_pages
                FROM docketwatch.dbo.documents d
                WHERE d.rel_path LIKE '%.pdf'
                AND d.isfound = 1
                AND (d.summary_ai IS NULL OR d.summary_ai = '')
                AND d.rel_path IS NOT NULL
                ORDER BY d.fk_case_event, d.doc_uid
            """
            if limit:
                query += f" OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
            cursor.execute(query)
        
        missing_docs = cursor.fetchall()
        
        if not missing_docs:
            return {'status': 'success', 'message': 'No PDFs missing summaries found', 'count': 0}
        
        # Group by case_event_id
        events_summary = {}
        for doc in missing_docs:
            event_id = doc.fk_case_event
            if event_id not in events_summary:
                events_summary[event_id] = []
            events_summary[event_id].append({
                'doc_uid': doc.doc_uid,
                'rel_path': doc.rel_path,
                'total_pages': doc.total_pages
            })
        
        return {
            'status': 'success',
            'total_docs': len(missing_docs),
            'total_events': len(events_summary),
            'events_summary': events_summary,
            'message': f'Found {len(missing_docs)} PDFs missing summaries across {len(events_summary)} events'
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


if __name__ == "__main__":
    main()

"""
USAGE INSTRUCTIONS:
==================

This modernized script should be placed in your main python directory:
u:\\docketwatch\\python\\modernized_pacer_processor.py

Then run it the same way as your original script:
python u:\\docketwatch\\python\\modernized_pacer_processor.py E39D680E-8618-4C32-8866-19829CF57D41

The script demonstrates:
1. Modern Python patterns (context managers, classes)
2. Integration with the new modular components
3. Same command-line interface as your original
4. Better error handling and logging
5. Workflow orchestration for complex operations

Once you're satisfied with this approach, you can replace your original
process_pacer_event_pdf.py with this modernized version.
"""
