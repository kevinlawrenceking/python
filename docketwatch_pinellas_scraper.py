#!/usr/bin/env python3
"""
Pinellas County Court Records Scraper
Searches for specific individuals and emails results if found.
Based on docketwatch_case_events.py pattern
"""

import os
import sys
import time
import json
import smtplib
import pyodbc
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Import from scraper_base for consistent logging
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scraper_base import log_message

# --- CONFIGURATION ---
SEARCH_URL = "https://courtrecords.mypinellasclerk.gov/MyCr/Cases/Search"
SCRIPT_NAME = "docketwatch_pinellas_scraper.py"

# Email configuration
FROM_EMAIL = "it@tmz.com"
TO_EMAIL = "kevin.king@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

# WebDriver configuration
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
IMPLICIT_WAIT = 10
PAGE_LOAD_TIMEOUT = 30

# Logging configuration
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\pinellas_scraper.log"
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Target individuals to search for
SEARCH_TARGETS = [
    {
        "first_name": "Terry",
        "last_name": "Bollea",
        "middle_name": "",
        "dob": ""
    }
    # Add more targets as needed
]

def setup_chrome_driver():
    """Initialize Chrome WebDriver with appropriate options"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # chrome_options.add_argument("--headless")  # Uncomment for headless mode
    
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(IMPLICIT_WAIT)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    
    return driver

def send_email(subject, body, html_body=None):
    """Send email notification"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        
        # Add plain text version
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)
        
        # Add HTML version if provided
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.send_message(msg)
        server.quit()
        
        logging.info(f"Email sent successfully to {TO_EMAIL}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

def search_individual(driver, cursor, fk_task_run, target):
    """Search for a specific individual"""
    try:
        first_name = target["first_name"]
        last_name = target["last_name"]
        middle_name = target.get("middle_name", "")
        dob = target.get("dob", "")
        
        log_message(cursor, fk_task_run, "INFO", f"Searching for {first_name} {last_name}")
        
        # Navigate to search page
        driver.get(SEARCH_URL)
        
        # Wait for page to load and find the form
        wait = WebDriverWait(driver, 10)
        
        # Ensure we're on the "Name" search tab
        party_type_dropdown = wait.until(
            EC.presence_of_element_located((By.ID, "PartyType"))
        )
        Select(party_type_dropdown).select_by_value("1")  # Select "Name"
        
        # Fill in Last Name (required)
        last_name_field = driver.find_element(By.ID, "LastName")
        last_name_field.clear()
        last_name_field.send_keys(last_name)
        
        # Fill in First Name (required)
        first_name_field = driver.find_element(By.ID, "FirstName")
        first_name_field.clear()
        first_name_field.send_keys(first_name)
        
        # Fill in Middle Name if provided
        if middle_name:
            middle_name_field = driver.find_element(By.ID, "MiddleName")
            middle_name_field.clear()
            middle_name_field.send_keys(middle_name)
        
        # Fill in DOB if provided
        if dob:
            dob_field = driver.find_element(By.ID, "DOB")
            dob_field.clear()
            dob_field.send_keys(dob)
        
        # Submit the form
        submit_button = driver.find_element(By.ID, "caseSearch")
        
        # Handle potential reCAPTCHA - wait a moment for it to process
        time.sleep(3)
        
        submit_button.click()
        
        # Wait for results page to load
        time.sleep(5)
        
        # Check for results
        results_found = check_for_results(driver, cursor, fk_task_run, target)
        
        return results_found
        
    except TimeoutException:
        error_msg = f"Timeout while searching for {target['first_name']} {target['last_name']}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        logging.error(error_msg)
        return False
        
    except Exception as e:
        error_msg = f"Error searching for {target['first_name']} {target['last_name']}: {str(e)}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        logging.error(error_msg)
        return False

def check_for_results(driver, cursor, fk_task_run, target):
    """Check if search returned any results and process them"""
    try:
        # Look for various indicators of results
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Check for common result indicators
        result_indicators = [
            'search-results',
            'case-result',
            'result-row',
            'results-table',
            'case-number',
            'case-link'
        ]
        
        has_results = False
        results_html = ""
        results_text = ""
        
        # Look for result containers
        for indicator in result_indicators:
            elements = soup.find_all(class_=lambda x: x and indicator in x) if soup else []
            if elements:
                has_results = True
                break
        
        # Also check for table rows that might contain case data
        if not has_results:
            tables = soup.find_all('table') if soup else []
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) > 1:  # More than just header row
                    has_results = True
                    break
        
        # Look for specific text patterns that indicate results
        if not has_results:
            result_patterns = [
                'case found',
                'search returned',
                'total cases',
                'case number',
                'filing date'
            ]
            
            page_text = soup.get_text().lower() if soup else ""
            for pattern in result_patterns:
                if pattern in page_text:
                    has_results = True
                    break
        
        # Check for "no results" messages
        no_result_patterns = [
            'no cases found',
            'no results',
            'no matches',
            '0 cases found',
            'search returned 0'
        ]
        
        page_text = soup.get_text().lower() if soup else ""
        for pattern in no_result_patterns:
            if pattern in page_text:
                has_results = False
                break
        
        if has_results:
            # Extract results for email
            results_html = str(soup) if soup else page_source
            results_text = soup.get_text() if soup else "Results found but could not parse content"
            
            target_name = f"{target['first_name']} {target['last_name']}"
            log_message(cursor, fk_task_run, "INFO", f"Results found for {target_name}")
            
            # Send email notification
            subject = f"Pinellas County Court Records Found: {target_name}"
            
            email_body = f"""
Search Results Found for {target_name}

Search Details:
- First Name: {target['first_name']}
- Last Name: {target['last_name']}
- Middle Name: {target.get('middle_name', 'N/A')}
- DOB: {target.get('dob', 'N/A')}
- Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Source: Pinellas County Court Records

Results:
{results_text[:2000]}...

View full results at: {driver.current_url}
"""
            
            # Create HTML version with better formatting
            html_body = f"""
<html>
<body>
<h2>Search Results Found for {target_name}</h2>

<h3>Search Details:</h3>
<ul>
    <li><strong>First Name:</strong> {target['first_name']}</li>
    <li><strong>Last Name:</strong> {target['last_name']}</li>
    <li><strong>Middle Name:</strong> {target.get('middle_name', 'N/A')}</li>
    <li><strong>DOB:</strong> {target.get('dob', 'N/A')}</li>
    <li><strong>Search Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
    <li><strong>Source:</strong> Pinellas County Court Records</li>
</ul>

<h3>Results:</h3>
<div style="border: 1px solid #ccc; padding: 10px; max-height: 400px; overflow-y: auto;">
{results_html[:5000]}...
</div>

<p><a href="{driver.current_url}">View full results</a></p>
</body>
</html>
"""
            
            send_email(subject, email_body, html_body)
            return True
        else:
            target_name = f"{target['first_name']} {target['last_name']}"
            log_message(cursor, fk_task_run, "INFO", f"No results found for {target_name}")
            return False
            
    except Exception as e:
        error_msg = f"Error checking results for {target['first_name']} {target['last_name']}: {str(e)}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        logging.error(error_msg)
        return False

def main():
    """Main execution function"""
    driver = None
    conn = None
    cursor = None
    fk_task_run = None
    
    try:
        # Setup database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        cursor = conn.cursor()
        
        # Create task run record
        cursor.execute("""
            INSERT INTO docketwatch.dbo.task_runs (fk_scheduled_task, started_at, status)
            VALUES ((SELECT id FROM docketwatch.dbo.scheduled_tasks WHERE script_name = ?), GETDATE(), 'running')
        """, (SCRIPT_NAME,))
        
        fk_task_run = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        conn.commit()
        
        log_message(cursor, fk_task_run, "INFO", "Starting Pinellas County scraper")
        
        # Setup WebDriver
        driver = setup_chrome_driver()
        
        results_found_count = 0
        total_searches = len(SEARCH_TARGETS)
        
        # Search for each target individual
        for target in SEARCH_TARGETS:
            try:
                if search_individual(driver, cursor, fk_task_run, target):
                    results_found_count += 1
                
                # Wait between searches to be respectful
                time.sleep(2)
                
            except Exception as e:
                error_msg = f"Failed to search for {target['first_name']} {target['last_name']}: {str(e)}"
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                logging.error(error_msg)
                continue
        
        # Update task run status
        cursor.execute("""
            UPDATE docketwatch.dbo.task_runs 
            SET completed_at = GETDATE(), status = 'completed', 
                notes = ? 
            WHERE id = ?
        """, (f"Searched {total_searches} targets, found results for {results_found_count}", fk_task_run))
        conn.commit()
        
        final_msg = f"Pinellas County scraper completed. Searched {total_searches} targets, found results for {results_found_count}"
        log_message(cursor, fk_task_run, "INFO", final_msg)
        logging.info(final_msg)
        
    except Exception as e:
        error_msg = f"Fatal error in Pinellas County scraper: {str(e)}"
        logging.error(error_msg)
        
        if cursor and fk_task_run:
            try:
                log_message(cursor, fk_task_run, "ERROR", error_msg)
                cursor.execute("""
                    UPDATE docketwatch.dbo.task_runs 
                    SET completed_at = GETDATE(), status = 'failed', notes = ? 
                    WHERE id = ?
                """, (error_msg, fk_task_run))
                conn.commit()
            except:
                pass
    
    finally:
        # Cleanup
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        if cursor:
            try:
                cursor.close()
            except:
                pass
        
        if conn:
            try:
                conn.close()
            except:
                pass

if __name__ == "__main__":
    main()
