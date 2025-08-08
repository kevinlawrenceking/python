"""
PDF Link Checker Script (Simplified Version)

PURPOSE:
This script checks if HTTP URLs for PDF documents are accessible and updates the database
to mark documents as found or not found based on HTTP response status.
This version has simplified error handling without email notifications for maximum reliability.

WORKFLOW:
1. Queries database for documents where isfound = 0
2. For each document, constructs the HTTP URL for the PDF
3. Makes HTTP HEAD request to check if PDF file exists
4. Updates isfound = 1 if PDF is accessible, keeps 0 if not found
5. Logs results and provides summary statistics

DATABASE UPDATES:
- Sets isfound = 1 for accessible PDF files
- Keeps isfound = 0 for inaccessible or missing files
- Updates in batches for efficiency
"""

import pyodbc
import requests
import logging
import os
import sys
from datetime import datetime

# Setup Logging
script_name = os.path.splitext(os.path.basename(__file__))[0]
log_dir = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, f"{script_name}_simple.log")
logging.basicConfig(
    filename=log_path, 
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# Also log to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Database Connection
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"

def get_db_connection():
    """Get database connection with proper error handling."""
    try:
        conn = pyodbc.connect(DB_CONNECTION)
        return conn, conn.cursor()
    except Exception as e:
        error_msg = f"Failed to connect to database: {e}"
        logger.error(error_msg)
        raise

def check_pdf_exists(url, timeout=10):
    """
    Check if a PDF file exists at the given URL.
    
    Args:
        url (str): The URL to check
        timeout (int): Request timeout in seconds
        
    Returns:
        tuple: (is_found, status_code, error_message)
    """
    try:
        # Use HEAD request to check if file exists without downloading
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        
        # Check if response is successful
        if response.status_code == 200:
            # Check content type to ensure it's a PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' in content_type or 'application/pdf' in content_type:
                return True, response.status_code, None
            else:
                return False, response.status_code, f"Not a PDF file. Content-Type: {content_type}"
        else:
            return False, response.status_code, f"HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, 0, "Request timeout"
    except requests.exceptions.ConnectionError:
        return False, 0, "Connection error"
    except requests.exceptions.RequestException as e:
        return False, 0, f"Request error: {str(e)}"
    except Exception as e:
        return False, 0, f"Unexpected error: {str(e)}"

def main():
    """Main function to check PDF links and update database."""
    logger.info("=== PDF Link Checker Started (Simple Version) ===")
    
    conn = None
    cursor = None
    
    try:
        # Get database connection
        conn, cursor = get_db_connection()
        logger.info("Database connection established")
        
        # Query for documents where isfound = 0
        logger.info("Querying for documents where isfound = 0...")
        cursor.execute("""
            SELECT doc_uid, 
                   isfound,
                   'http://docketwatch.tmz.local/docs/cases/' + 
                   CAST(d.fk_case AS VARCHAR) + '/E' + 
                   CAST(d.doc_id AS VARCHAR) + '.pdf' AS http_url,
                   d.fk_case,
                   d.doc_id
            FROM documents d 
            WHERE isfound = 0
            ORDER BY d.fk_case, d.doc_id
        """)
        
        rows = cursor.fetchall()
        total_documents = len(rows)
        
        if total_documents == 0:
            logger.info("No documents found with isfound = 0")
            print("No documents found with isfound = 0")
            return
            
        logger.info(f"Found {total_documents} documents to check")
        print(f"Found {total_documents} documents to check")
        
        # Counters for statistics
        found_count = 0
        not_found_count = 0
        error_count = 0
        batch_size = 50
        
        # Process documents
        for i, row in enumerate(rows, 1):
            doc_uid = row.doc_uid
            current_isfound = row.isfound
            http_url = row.http_url
            fk_case = row.fk_case
            doc_id = row.doc_id
            
            if i % 100 == 0 or i == 1:
                print(f"Processing {i}/{total_documents}: Case {fk_case}, Doc {doc_id}")
            
            logger.info(f"Processing {i}/{total_documents}: Case {fk_case}, Doc {doc_id}")
            logger.debug(f"Checking URL: {http_url}")
            
            # Check if PDF exists
            is_found, status_code, error_msg = check_pdf_exists(http_url)
            
            if is_found:
                # Update database to mark as found
                try:
                    cursor.execute("""
                        UPDATE documents 
                        SET isfound = 1, 
                            date_checked = GETDATE()
                        WHERE doc_uid = ?
                    """, (doc_uid,))
                    
                    found_count += 1
                    logger.info(f"✓ PDF found and marked: Case {fk_case}, Doc {doc_id}")
                    
                except Exception as e:
                    error_msg = f"Database error updating doc_uid {doc_uid}: {e}"
                    logger.error(error_msg)
                    error_count += 1
                    
            else:
                # Log why PDF was not found, but don't update database (keep isfound = 0)
                not_found_count += 1
                logger.debug(f"✗ PDF not found: Case {fk_case}, Doc {doc_id} - {error_msg or f'HTTP {status_code}'}")
            
            # Commit in batches for efficiency
            if i % batch_size == 0:
                conn.commit()
                logger.info(f"Committed batch at {i}/{total_documents}")
                print(f"Progress: {i}/{total_documents} ({(i/total_documents)*100:.1f}%) - Found: {found_count}, Not Found: {not_found_count}")
        
        # Final commit
        conn.commit()
        logger.info("Final commit completed")
        
        # Log summary statistics
        logger.info("=== PDF Link Check Summary ===")
        logger.info(f"Total documents checked: {total_documents}")
        logger.info(f"PDFs found and marked: {found_count}")
        logger.info(f"PDFs not found: {not_found_count}")
        logger.info(f"Errors encountered: {error_count}")
        if total_documents > 0:
            logger.info(f"Success rate: {(found_count/total_documents)*100:.1f}%")
        
        print("\n=== PDF Link Check Summary ===")
        print(f"Total documents checked: {total_documents}")
        print(f"PDFs found and marked: {found_count}")
        print(f"PDFs not found: {not_found_count}")
        print(f"Errors encountered: {error_count}")
        if total_documents > 0:
            print(f"Success rate: {(found_count/total_documents)*100:.1f}%")
        print("PDF Link Checker completed successfully!")
        
    except Exception as e:
        error_msg = f"Critical error in PDF link checker: {str(e)}"
        logger.exception(error_msg)
        print(f"Error: {error_msg}")
        return 1
        
    finally:
        # Cleanup
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            logger.info("Database connection closed")
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
