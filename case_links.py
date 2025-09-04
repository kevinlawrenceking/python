#!/usr/bin/env python3
"""
TMZ Case Links Scraper
Finds TMZ articles related to tracked cases and stores the links in the database.
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse
import pyodbc
import logging
import os
import time
from datetime import datetime
import sys

# === LOGGING SETUP ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"

# Create a more comprehensive logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)  # Also log to console
    ]
)

logger = logging.getLogger(__name__)

# === CONFIGURATION ===
DSN = "Docketwatch"
TMZ_BASE_URL = "https://www.tmz.com"
SEARCH_URL_TEMPLATE = "https://www.tmz.com/search/?q={}"
REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 3
DELAY_BETWEEN_REQUESTS = 1  # seconds

# === DATABASE CONNECTION FUNCTIONS ===
def get_database_connection():
    """Establish database connection with error handling"""
    try:
        conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        logger.info("Database connection established successfully")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def get_unlinked_cases(cursor):
    """Query cases that don't have links yet"""
    try:
        query = """
            SELECT TOP 10 c.id, c.case_name
            FROM docketwatch.dbo.cases c
            INNER JOIN docketwatch.dbo.case_events ce ON c.id = ce.fk_case
            WHERE c.id NOT IN (SELECT fk_case FROM docketwatch.dbo.case_links) 
            AND c.status = 'Tracked'
            AND CAST(ce.created_at AS DATE) = CAST(GETDATE() AS DATE)
            GROUP BY c.id, c.case_name
            ORDER BY MAX(ce.created_at) DESC
        """
        cursor.execute(query)
        cases = cursor.fetchall()
        logger.info(f"Found {len(cases)} unlinked tracked cases with today's events to process")
        
        # Log some sample case names for debugging
        if cases:
            logger.info(f"Sample cases: {[case[1][:50] + '...' if len(case[1]) > 50 else case[1] for case in cases[:3]]}")
        
        return cases
    except Exception as e:
        logger.error(f"Failed to query unlinked cases: {e}")
        raise

# === URL FORMATTING FUNCTIONS ===
def format_case_name(case_name):
    """Format case name for URL encoding with better handling"""
    if not case_name:
        logger.warning("Empty case name provided")
        return ""
    
    # Clean up the case name
    cleaned_name = case_name.strip()
    logger.debug(f"Formatting case name: '{cleaned_name}'")
    
    # URL encode the case name
    formatted = urllib.parse.quote_plus(cleaned_name)
    logger.debug(f"Formatted case name: '{formatted}'")
    
    return formatted

def build_search_url(case_name):
    """Build TMZ search URL"""
    formatted_name = format_case_name(case_name)
    if not formatted_name:
        return None
    
    url = SEARCH_URL_TEMPLATE.format(formatted_name)
    logger.debug(f"Built search URL: {url}")
    return url

# === WEB SCRAPING FUNCTIONS ===
def make_request_with_retry(url, max_retries=RETRY_ATTEMPTS):
    """Make HTTP request with retry logic"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Making request to {url} (attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            logger.debug(f"Request successful, received {len(response.content)} bytes")
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"All {max_retries} request attempts failed for URL: {url}")
                raise
    return None

def scrape_tmz_search_results(case_id, case_name):
    """Scrape TMZ search results for a given case"""
    logger.info(f"Scraping TMZ results for case ID {case_id}: '{case_name}'")
    
    search_url = build_search_url(case_name)
    if not search_url:
        logger.warning(f"Could not build search URL for case {case_id}")
        return []

    try:
        response = make_request_with_retry(search_url)
        if not response:
            return []
        
        # Add delay to be respectful to the server
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
    except Exception as e:
        logger.error(f"Request failed for case {case_id} - {case_name}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    cards = soup.select("article.gridler__card")
    logger.debug(f"Found {len(cards)} article cards on search results page")

    results = []
    for i, card in enumerate(cards):
        try:
            link_tag = card.select_one("a.gridler__card-link")
            title_tag = card.select_one("h4.gridler__card-title")
            img_tag = card.select_one("img")

            if link_tag and title_tag and img_tag:
                # Ensure URLs are absolute
                case_url = link_tag['href']
                if case_url.startswith('/'):
                    case_url = TMZ_BASE_URL + case_url
                
                image_url = img_tag['src']
                if image_url.startswith('/'):
                    image_url = TMZ_BASE_URL + image_url
                
                result = {
                    "fk_case": case_id,
                    "case_url": case_url,
                    "title": title_tag.get_text(strip=True),
                    "image_url": image_url
                }
                results.append(result)
                logger.debug(f"Parsed article {i+1}: '{result['title'][:50]}...'")
            else:
                logger.debug(f"Skipping incomplete article card {i+1} (missing required elements)")
                
        except Exception as parse_err:
            logger.warning(f"Failed to parse article card {i+1} for case {case_id}: {parse_err}")

    logger.info(f"Successfully parsed {len(results)} articles for case {case_id}")
    return results

# === DATABASE INSERTION FUNCTIONS ===
def insert_case_links(cursor, case_links):
    """Insert case links into database with error handling"""
    if not case_links:
        logger.debug("No case links to insert")
        return 0
    
    insert_sql = """
        INSERT INTO docketwatch.dbo.case_links (fk_case, case_url, title, image_url)
        VALUES (?, ?, ?, ?)
    """
    
    inserted_count = 0
    for link in case_links:
        try:
            cursor.execute(insert_sql, 
                         link["fk_case"], 
                         link["case_url"], 
                         link["title"], 
                         link["image_url"])
            inserted_count += 1
            logger.debug(f"Inserted link: '{link['title'][:50]}...' -> {link['case_url']}")
        except Exception as e:
            logger.error(f"Failed to insert link for case {link['fk_case']}: {e}")
            logger.error(f"Link data: {link}")
    
    return inserted_count

# === MAIN EXECUTION ===
def main():
    """Main execution function"""
    start_time = datetime.now()
    logger.info(f"Starting TMZ case links scraper at {start_time}")
    
    conn = None
    cursor = None
    total_cases_processed = 0
    total_links_inserted = 0
    
    try:
        # === DATABASE CONNECTION ===
        conn = get_database_connection()
        cursor = conn.cursor()

        # === QUERY CASES WITHOUT LINKS ===
        cases = get_unlinked_cases(cursor)
        
        if not cases:
            logger.info("No unlinked cases found. Script completed.")
            return

        # === PROCESS EACH CASE ===
        for i, (case_id, case_name) in enumerate(cases, 1):
            try:
                logger.info(f"Processing case {i}/{len(cases)}: ID {case_id}")
                
                # Scrape TMZ search results
                matches = scrape_tmz_search_results(case_id, case_name)
                
                # Insert results into database
                if matches:
                    inserted_count = insert_case_links(cursor, matches)
                    conn.commit()
                    total_links_inserted += inserted_count
                    logger.info(f"Successfully inserted {inserted_count} links for case ID {case_id}")
                else:
                    logger.info(f"No TMZ articles found for case ID {case_id}")
                
                total_cases_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing case {case_id}: {e}")
                try:
                    conn.rollback()
                    logger.info(f"Rolled back transaction for case {case_id}")
                except:
                    pass
                continue

        # === FINAL SUMMARY ===
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("=" * 60)
        logger.info("SCRIPT EXECUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Start time: {start_time}")
        logger.info(f"End time: {end_time}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total cases processed: {total_cases_processed}")
        logger.info(f"Total links inserted: {total_links_inserted}")
        logger.info(f"Average links per case: {total_links_inserted / max(total_cases_processed, 1):.2f}")
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        raise
        
    finally:
        # Cleanup
        if cursor:
            try:
                cursor.close()
                logger.debug("Database cursor closed")
            except:
                pass
        
        if conn:
            try:
                conn.close()
                logger.debug("Database connection closed")
            except:
                pass

if __name__ == "__main__":
    main()
