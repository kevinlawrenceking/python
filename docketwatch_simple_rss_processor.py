#!/usr/bin/env python3
"""
DocketWatch Simple RSS Processor

OVERVIEW:
A simplified version that runs the complete workflow without complex database schema dependencies:
1. RSS Trigger - Monitors PACER RSS feeds and downloads PDFs
2. PDF Retry - Retries failed downloads using direct downloader
3. Basic reporting

This script avoids database schema compatibility issues while providing the core functionality.

USAGE:
    python docketwatch_simple_rss_processor.py

SCHEDULING:
Run every 15-30 minutes for optimal RSS monitoring coverage.
"""

import sys
import os
import subprocess
import logging
import time
import pyodbc
from datetime import datetime

from scraper_base import log_message
from error_notification_system import create_error_notifier

# =========================
# Configuration
# =========================

script_filename = os.path.splitext(os.path.basename(__file__))[0]
error_notifier = create_error_notifier(script_filename)

LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Script paths
RSS_TRIGGER_SCRIPT = r"u:\docketwatch\python\docketwatch_rss_trigger_enhanced.py"
METADATA_EXTRACTOR = r"u:\docketwatch\python\extract_pacer_pdf_metadata.py"
PDF_PROCESSOR = r"u:\docketwatch\python\process_pacer_event_pdf_final.py"

# Processing configuration
ENABLE_RSS_MONITORING = True
ENABLE_RETRY_FAILED_PDFS = True

# Timeouts (in seconds)
RSS_SCRIPT_TIMEOUT = 1800  # 30 minutes

def setup_simple_database_connection():
    """Setup database connection with simple task run tracking"""
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        # Use simple task run ID from existing RSS triggers
        cursor.execute("""
            SELECT TOP 1 r.id as fk_task_run
            FROM docketwatch.dbo.task_runs r
            INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
            WHERE s.filename LIKE '%rss%'
            ORDER BY r.id DESC
        """)
        task_run = cursor.fetchone()
        fk_task_run = task_run[0] if task_run else 1
        
        return conn, cursor, fk_task_run
        
    except Exception as e:
        error_msg = f"Database setup failed: {e}"
        print(f"CRITICAL: {error_msg}")
        error_notifier.log_database_error(error_msg)
        raise

def run_rss_monitoring(cursor, fk_task_run):
    """Run the RSS monitoring and processing script"""
    if not ENABLE_RSS_MONITORING:
        log_message(cursor, fk_task_run, "INFO", "RSS monitoring disabled")
        return True
    
    try:
        log_message(cursor, fk_task_run, "INFO", "Starting RSS monitoring and processing")
        
        result = subprocess.run(
            ["python", RSS_TRIGGER_SCRIPT],
            cwd=r"u:\docketwatch\python",
            capture_output=True,
            text=True,
            timeout=RSS_SCRIPT_TIMEOUT
        )
        
        if result.returncode == 0:
            log_message(cursor, fk_task_run, "INFO", "RSS monitoring completed successfully")
            return True
        else:
            error_msg = f"RSS monitoring failed: {result.stderr}"
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            return False
            
    except subprocess.TimeoutExpired:
        error_msg = "RSS monitoring timeout"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        return False
        
    except Exception as e:
        error_msg = f"RSS monitoring error: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        return False

def retry_recent_failed_pdfs(cursor, fk_task_run):
    """Retry failed PDF downloads for recent case events using the proven omega approach"""
    if not ENABLE_RETRY_FAILED_PDFS:
        log_message(cursor, fk_task_run, "INFO", "PDF retry disabled")
        return True
    
    try:
        log_message(cursor, fk_task_run, "INFO", "Starting retry of recent failed PDF downloads using omega approach")
        
        # Use the same proven query from omega script
        cursor.execute("""
            SELECT TOP 10 
                ce.id,
                ce.event_no,
                c.case_number,
                CASE 
                    WHEN d.doc_uid IS NULL THEN 'NO_DOCS'
                    WHEN d.rel_path = 'pending' THEN 'PENDING'
                    ELSE 'OTHER'
                END as status,
                COUNT(d.doc_uid) as doc_count
            FROM docketwatch.dbo.case_events ce
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
            LEFT JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_event
            WHERE t.tool_name = 'Pacer'
                AND ce.event_url IS NOT NULL 
                AND ce.event_url != ''
                AND ce.event_date >= DATEADD(day, -2, GETDATE())  -- Last 2 days
                AND (
                    d.doc_uid IS NULL  -- No documents (need metadata)
                    OR d.rel_path = 'pending'  -- Pending documents (need download)
                )
            GROUP BY ce.id, 
                ce.event_no,
                c.case_number,
                CASE 
                    WHEN d.doc_uid IS NULL THEN 'NO_DOCS'
                    WHEN d.rel_path = 'pending' THEN 'PENDING'
                    ELSE 'OTHER'
                END
            ORDER BY ce.event_date DESC, ce.id DESC
        """)
        
        recent_events = cursor.fetchall()
        
        if not recent_events:
            log_message(cursor, fk_task_run, "INFO", "No recent case events found for PDF retry")
            return True
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(recent_events)} recent case events to process with omega approach")
        
        success_count = 0
        
        for event_row in recent_events:
            case_event_id, event_no, case_number, status, doc_count = event_row
            
            try:
                log_message(cursor, fk_task_run, "INFO", 
                           f"Processing case event {case_event_id} (Event {event_no}, Case {case_number}, Status: {status})")
                
                # STEP 1: Always run metadata extraction first (omega approach)
                log_message(cursor, fk_task_run, "INFO", f"Step 1: Running metadata extraction for {case_event_id}")
                
                result1 = subprocess.run(
                    ["python", METADATA_EXTRACTOR, str(case_event_id)],
                    cwd=r"u:\docketwatch\python",
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes
                )
                
                if result1.returncode == 0:
                    log_message(cursor, fk_task_run, "INFO", f"Metadata extraction completed for {case_event_id}")
                    time.sleep(3)  # Wait before next step (omega timing)
                    
                    # STEP 2: Run PDF download (omega approach)
                    log_message(cursor, fk_task_run, "INFO", f"Step 2: Running PDF download for {case_event_id}")
                    
                    result2 = subprocess.run(
                        ["python", PDF_PROCESSOR, str(case_event_id)],
                        cwd=r"u:\docketwatch\python",
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minutes
                    )
                    
                    if result2.returncode == 0:
                        success_count += 1
                        log_message(cursor, fk_task_run, "INFO", 
                                   f"Successfully processed case event {case_event_id} using omega approach")
                    else:
                        log_message(cursor, fk_task_run, "WARNING", 
                                   f"PDF download failed for case event {case_event_id}")
                else:
                    log_message(cursor, fk_task_run, "WARNING", 
                               f"Metadata extraction failed for case event {case_event_id}")
                
                # Delay between case events (omega timing)
                time.sleep(3)
                
            except subprocess.TimeoutExpired:
                log_message(cursor, fk_task_run, "WARNING", 
                           f"Timeout processing case event {case_event_id}")
            except Exception as retry_error:
                log_message(cursor, fk_task_run, "WARNING", 
                           f"Error processing case event {case_event_id}: {retry_error}")
        
        log_message(cursor, fk_task_run, "INFO", 
                   f"Omega approach retry completed. Processed: {len(recent_events)}, Successful: {success_count}")
        
        return True
        
    except Exception as e:
        error_msg = f"Omega approach retry process error: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        return False

def generate_simple_summary(cursor, fk_task_run):
    """Generate a simple processing summary"""
    try:
        # Get basic statistics (simplified query)
        cursor.execute("""
            SELECT 
                COUNT(*) as total_docs,
                SUM(CASE WHEN rel_path IS NOT NULL AND rel_path != 'pending' THEN 1 ELSE 0 END) as downloaded,
                SUM(CASE WHEN rel_path = 'pending' THEN 1 ELSE 0 END) as pending
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE c.fk_tool = 2  -- PACER
        """)
        
        stats = cursor.fetchone()
        total_docs, downloaded, pending = stats
        
        summary_msg = f"""
        Processing Summary:
        - Total PACER documents: {total_docs}
        - Successfully downloaded: {downloaded}
        - Pending downloads: {pending}
        """
        
        log_message(cursor, fk_task_run, "INFO", summary_msg)
        
        return {
            'total_docs': total_docs,
            'downloaded': downloaded,
            'pending': pending
        }
        
    except Exception as e:
        error_msg = f"Error generating summary: {e}"
        log_message(cursor, fk_task_run, "WARNING", error_msg)
        return {}

def main():
    """Main processing function"""
    print(f"Starting DocketWatch Simple RSS Processor at {datetime.now()}")
    print(f"Logging to: {LOG_FILE}")
    
    conn = None
    cursor = None
    fk_task_run = None
    
    try:
        # Setup database connection
        conn, cursor, fk_task_run = setup_simple_database_connection()
        
        log_message(cursor, fk_task_run, "INFO", "DocketWatch Simple RSS Processor started")
        
        # Step 1: Run RSS monitoring and processing
        rss_success = run_rss_monitoring(cursor, fk_task_run)
        
        # Step 2: Retry failed PDF downloads for recent events
        retry_success = retry_recent_failed_pdfs(cursor, fk_task_run)
        
        # Step 3: Generate simple summary
        summary_stats = generate_simple_summary(cursor, fk_task_run)
        
        # Determine overall status
        overall_success = rss_success and retry_success
        status = "Completed successfully" if overall_success else "Completed with warnings"
        
        log_message(cursor, fk_task_run, "INFO", f"DocketWatch Simple RSS Processor finished: {status}")
        
        print(f"\nProcessing completed at {datetime.now()}")
        print(f"Status: {status}")
        if summary_stats:
            print(f"Total PACER documents: {summary_stats.get('total_docs', 0)}")
            print(f"Successfully downloaded: {summary_stats.get('downloaded', 0)}")
            print(f"Pending downloads: {summary_stats.get('pending', 0)}")
        
    except Exception as e:
        error_msg = f"Critical error in main processing: {e}"
        print(f"CRITICAL: {error_msg}")
        
        try:
            if cursor and fk_task_run:
                log_message(cursor, fk_task_run, "ERROR", error_msg)
        except:
            pass
        
        error_notifier.log_critical_error(
            error_msg,
            fk_task_run=fk_task_run,
            additional_context="Simple RSS processor main function failed"
        )
        raise
        
    finally:
        # Cleanup database connections
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            print("Database connections closed")
        except Exception as cleanup_error:
            print(f"Warning: Database cleanup error: {cleanup_error}")

if __name__ == "__main__":
    main()