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

import json
import base64
from urllib.parse import urljoin, urlparse

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


def download_pdf_from_iframe(driver, cursor, fk_task_run, timeout=20):
    """
    Capture the first streamed PDF bytes from the PACER iframe using Chrome DevTools Protocol.
    Returns bytes or None.
    """
    try:
        # Enable CDP Network
        try:
            driver.execute_cdp_cmd("Network.enable", {})
        except Exception as e:
            log_message(cursor, fk_task_run, "WARNING", f"Network.enable failed: {e}")
        
        import time, json, base64
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline:
            try:
                entries = driver.get_log("performance")
            except Exception:
                entries = []
            for entry in entries:
                try:
                    msg = json.loads(entry.get("message","")).get("message", {})
                except Exception:
                    continue
                if msg.get("method") != "Network.responseReceived":
                    continue
                params = msg.get("params", {})
                resp = params.get("response", {})
                url = resp.get("url","")
                mime = resp.get("mimeType","")
                req_id = params.get("requestId")
                if req_id in seen:
                    continue
                if ("show_temp.pl" in url or "/doc1/" in url) and "application/pdf" in mime:
                    seen.add(req_id)
                    try:
                        body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                        data = body.get("body", "")
                        return base64.b64decode(data) if body.get("base64Encoded") else data.encode("utf-8", "ignore")
                    except Exception as e:
                        log_message(cursor, fk_task_run, "ERROR", f"Network.getResponseBody failed: {e}")
                        return None
            time.sleep(0.2)
        log_message(cursor, fk_task_run, "WARNING", "Timed out capturing PDF from CDP")
        return None
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Error capturing PDF via CDP: {e}")
        return None

def download_from_billing_form(driver, cursor, fk_task_run):
    """
    On PACER billing page with 'View Document', do NOT click.
    Parse the form action (/doc1/...), POST it once with session cookies, and return PDF bytes.
    """
    try:
        from selenium.webdriver.common.by import By
        # Find the billing form action
        form = driver.find_element(By.XPATH, "//form[contains(@action, '/doc1/')]")
        action_url = form.get_attribute("action")
        if not action_url:
            log_message(cursor, fk_task_run, "ERROR", "Billing form action not found")
            return None

        # Build requests session with Selenium cookies
        import requests
        s = requests.Session()
        # Use current domain to scope cookies if domains are missing
        from urllib.parse import urlparse
        base_host = urlparse(driver.current_url).hostname
        for c in driver.get_cookies():
            s.cookies.set(c["name"], c["value"], domain=c.get("domain") or base_host)

        headers = {
            "Referer": driver.current_url,
            "User-Agent": driver.execute_script("return navigator.userAgent;"),
            "Accept": "application/pdf,application/octet-stream,*/*;q=0.9",
        }
        r = s.post(action_url, headers=headers, timeout=120, allow_redirects=True)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type","").lower()
        if "application/pdf" in ctype or r.content.startswith(b"%PDF"):
            return r.content
        # Some courts 302 to a /doc1 URL that then streams the PDF on GET. Follow once.
        if "/doc1/" in r.url and r.url != action_url:
            r2 = s.get(r.url, headers={"Referer": action_url, "User-Agent": headers["User-Agent"]}, timeout=120, allow_redirects=True)
            if "application/pdf" in r2.headers.get("Content-Type","").lower() or r2.content.startswith(b"%PDF"):
                return r2.content
        log_message(cursor, fk_task_run, "ERROR", f"Billing POST did not return PDF. Content-Type={ctype}")
        return None
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"download_from_billing_form failed: {e}")
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
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
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
                driver.execute_cdp_cmd("Network.enable", {});
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
                    log_message(cursor, fk_task_run, "INFO", "PACER billing page detected; fetching via POST")
                    pdf_content = download_from_billing_form(driver, cursor, fk_task_run)
                    if pdf_content:
                        with open(final_dest_path, 'wb') as f:
                            f.write(pdf_content)
                        log_message(cursor, fk_task_run, "INFO", f"PDF saved via billing POST: {filename} ({len(pdf_content)} bytes)")
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
                        log_message(cursor, fk_task_run, "WARNING", "Billing POST failed to return PDF; continuing to try iframe capture")

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