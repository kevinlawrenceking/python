import pyodbc
import subprocess
import concurrent.futures
import time
import logging
import os
import sys
import argparse
import psutil
from datetime import datetime

# Database connection parameters
DB_CONNECTION_STRING = "DSN=Docketwatch;TrustServerCertificate=yes;"

def get_db_connection():
    """Create and return a new database connection with appropriate settings."""
    try:
        conn = pyodbc.connect(DB_CONNECTION_STRING, timeout=30)
        return conn
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise

def execute_query(query, params=None, fetch_mode="all"):
    """
    Execute a database query with proper connection handling and error management.
    
    Args:
        query: SQL query string
        params: Parameters for the query (tuple)
        fetch_mode: "all", "one", or None (for updates)
    
    Returns:
        Query results or affected row count
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if fetch_mode == "all":
            result = cursor.fetchall()
        elif fetch_mode == "one":
            result = cursor.fetchone()
        else:
            # For INSERT, UPDATE, DELETE
            conn.commit()
            result = cursor.rowcount
            
        return result
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Database error: {str(e)}")
        logging.error(f"Query: {query}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_tracked_cases():
    """Fetch unsummarized tracked cases with priority sorting."""
    try:
        query = """
            SELECT TOP 30 id 
            FROM docketwatch.dbo.cases 
            WHERE fk_tool = 2 
              AND status = 'Tracked' 
              AND (summarize IS NULL OR summarize = 'Summary failed: Timeout')
              AND (summary_attempted_at IS NULL OR 
                   summary_attempted_at < DATEADD(HOUR, -1, GETDATE())) 
            ORDER BY fk_priority DESC
        """
        
        rows = execute_query(query)
        ids = [row[0] for row in rows]
        logging.info(f"Retrieved {len(ids)} cases needing summarization")
        return ids
    except Exception as e:
        logging.error(f"Error retrieving cases: {e}")
        return []

def run_summarizer(case_id):
    """Run the case summarizer with improved error handling and timeout."""
    logging.info(f"Starting summarization for case {case_id}...")
    print(f"Summarizing case {case_id}...")
    
    # Mark the case as being processed
    try:
        query = """
            UPDATE docketwatch.dbo.cases
            SET summarize = 'Attempting summary', 
                summary_attempted_at = GETDATE()
            WHERE id = ?
        """
        execute_query(query, (case_id,))
    except Exception as e:
        error_msg = f"Failed to mark case {case_id} as 'Attempting summary': {e}"
        logging.error(error_msg)
        print(f"[!] {error_msg}")
        raise  # Re-raise to be caught in the executor

    # Run the summarizer with timeout and capture output
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            logging.info(f"Case {case_id}: Attempt {attempt}/{max_attempts}")
            
            # Run the summarizer with a timeout
            result = subprocess.run(
                [
                    "python",
                    r"\\10.146.176.84\general\docketwatch\python\pacer_case_summarizer.py",
                    "--case-id",
                    str(case_id)
                ],
                capture_output=True,
                text=True,
                timeout=600  # 10-minute timeout
            )
            
            # Check if the process was successful
            if result.returncode == 0:
                logging.info(f"Case {case_id}: Successfully summarized")
                if result.stdout:
                    logging.debug(f"Case {case_id} stdout: {result.stdout[:500]}...")
                return True
            else:
                error_msg = f"Case {case_id}: Summarizer failed with code {result.returncode}"
                if result.stderr:
                    error_msg += f", Error: {result.stderr}"
                logging.error(error_msg)
                
                # Only retry if this wasn't the last attempt
                if attempt < max_attempts:
                    logging.info(f"Case {case_id}: Will retry in 5 seconds...")
                    time.sleep(5)
                else:
                    # Mark as failed in the database on final attempt
                    try:
                        execute_query("""
                            UPDATE docketwatch.dbo.cases
                            SET summarize = 'Summary failed: Process error'
                            WHERE id = ?
                        """, (case_id,))
                    except Exception as db_e:
                        logging.error(f"Failed to update failure status for case {case_id}: {db_e}")
                    
                    raise Exception(error_msg)
        
        except subprocess.TimeoutExpired:
            error_msg = f"Case {case_id}: Summarizer timed out after 10 minutes"
            logging.error(error_msg)
            
            # Mark as timed out in the database if this is the final attempt
            if attempt == max_attempts:
                try:
                    execute_query("""
                        UPDATE docketwatch.dbo.cases
                        SET summarize = 'Summary failed: Timeout'
                        WHERE id = ?
                    """, (case_id,))
                except Exception as db_e:
                    logging.error(f"Failed to update timeout status for case {case_id}: {db_e}")
                
                raise Exception(error_msg)
            else:
                logging.info(f"Case {case_id}: Will retry after timeout in 5 seconds...")
                time.sleep(5)
        
        except Exception as e:
            error_msg = f"Case {case_id}: Unexpected error: {e}"
            logging.error(error_msg)
            
            if attempt == max_attempts:
                # Mark as failed in the database on final attempt
                try:
                    execute_query("""
                        UPDATE docketwatch.dbo.cases
                        SET summarize = 'Summary failed: Unknown error'
                        WHERE id = ?
                    """, (case_id,))
                except Exception as db_e:
                    logging.error(f"Failed to update error status for case {case_id}: {db_e}")
                
                raise Exception(error_msg)
            else:
                logging.info(f"Case {case_id}: Will retry after error in 5 seconds...")
                time.sleep(5)


# Setup logging
LOG_DIR = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "batch_case_summarizer.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def check_system_resources():
    """Check if system has enough resources to run the batch process."""
    # Check available memory (require at least 2GB free)
    mem = psutil.virtual_memory()
    if mem.available < 2 * 1024 * 1024 * 1024:  # 2GB
        logging.warning(f"Low memory: {mem.available / (1024*1024*1024):.1f}GB available")
        return False
        
    # Check CPU usage (require at least 2 cores with < 80% usage)
    cpu_usage = psutil.cpu_percent(interval=1)
    if cpu_usage > 80:
        logging.warning(f"High CPU usage: {cpu_usage}%")
        return False
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Batch process case summarization")
    parser.add_argument("--workers", type=int, default=3, help="Maximum number of concurrent workers")
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of cases to process")
    parser.add_argument("--case-id", type=str, help="Process specific case ID only")
    parser.add_argument("--force", action="store_true", help="Force processing even with low resources")
    args = parser.parse_args()
    
    # Initialize
    start_time = datetime.now()
    logging.info(f"Batch summarizer started with {args.workers} workers, limit={args.limit}")
    
    # Check system resources unless forced
    if not args.force and not check_system_resources():
        logging.error("Insufficient system resources. Use --force to override.")
        print("ERROR: Insufficient system resources. Use --force to override.")
        return 1
    
    # Get cases to process
    if args.case_id:
        case_ids = [args.case_id]
        logging.info(f"Processing single case ID: {args.case_id}")
    else:
        case_ids = get_tracked_cases()[:args.limit]
        
    if not case_ids:
        logging.info("No cases found to process.")
        print("No cases found to process.")
        return 0
        
    logging.info(f"Found {len(case_ids)} cases to summarize.")
    print(f"Found {len(case_ids)} cases to summarize.")
    
    # Set maximum workers based on system
    max_workers = min(args.workers, os.cpu_count() or 4)
    logging.info(f"Using {max_workers} workers")
    
    # Process cases in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks and store the futures
        futures = {executor.submit(run_summarizer, cid): cid for cid in case_ids}
        
        # Process results as they complete
        completed = 0
        failed = 0
        for future in concurrent.futures.as_completed(futures):
            case_id = futures[future]
            try:
                # Get the result (or exception if one was raised)
                future.result()
                completed += 1
                logging.info(f"Completed {completed}/{len(case_ids)} - Case ID: {case_id}")
                print(f"✓ Completed case {case_id} ({completed}/{len(case_ids)})")
            except Exception as e:
                failed += 1
                logging.error(f"Error processing case {case_id}: {e}")
                print(f"✗ Failed case {case_id}: {str(e)[:100]}...")
    
    duration = datetime.now() - start_time
    result_msg = (f"Batch processing completed in {duration}. "
                 f"Processed {len(case_ids)} cases: {completed} successful, {failed} failed.")
    logging.info(result_msg)
    print(result_msg)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.warning("Process interrupted by user")
        print("\nProcess interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)
