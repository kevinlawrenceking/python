#!/usr/bin/env python3
"""
DocketWatch Complete RSS Processor

OVERVIEW:
This is the master script that runs the complete workflow:
1. RSS Trigger - Monitors PACER RSS feeds for new case events
2. PDF Download - Downloads PDFs from PACER for new events 
3. Document Summarization - Generates AI summaries of downloaded documents
4. Email Alerts - Sends enhanced notifications with summaries

This script orchestrates the entire end-to-end process from RSS monitoring
to final summarized documents and notifications.

USAGE:
    python docketwatch_complete_rss_processor.py

SCHEDULING:
Run every 15-30 minutes for optimal RSS monitoring coverage.

COMPONENTS:
- docketwatch_rss_trigger_enhanced.py (RSS monitoring + orchestration)
- pacer_pdf_direct_downloader.py (PDF extraction for iframe scenarios)
- summarize_document_event.py (AI-powered document summarization)

FEATURES:
- Handles PACER's iframe PDF delivery mechanism
- Robust error handling and recovery
- Comprehensive logging and notifications
- Automatic retry for failed downloads
- Email alerts with PDF summaries included
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
DIRECT_PDF_DOWNLOADER = r"u:\docketwatch\python\pacer_pdf_direct_downloader.py"
BATCH_PDF_PROCESSOR = r"u:\docketwatch\python\process_pacer_event_pdf_final.py"

# Processing configuration
ENABLE_RSS_MONITORING = True
ENABLE_BATCH_PDF_PROCESSING = True
ENABLE_RETRY_FAILED_PDFS = True

# Timeouts (in seconds)
RSS_SCRIPT_TIMEOUT = 1800  # 30 minutes
PDF_PROCESSING_TIMEOUT = 3600  # 60 minutes

def setup_database_connection():
    """Setup database connection and task run tracking"""
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        # Use the existing RSS trigger approach for task run tracking
        cursor.execute("""
            SELECT TOP 1 r.id as fk_task_run
            FROM docketwatch.dbo.task_runs r
            INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
            WHERE s.filename LIKE '%rss%'
            ORDER BY r.id DESC
        """)
        task_run = cursor.fetchone()
        fk_task_run = task_run[0] if task_run else 1  # Fallback to ID 1
        
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
            error_notifier.log_error("RSS Monitoring Failed", error_msg, fk_task_run=fk_task_run)
            return False
            
    except subprocess.TimeoutExpired:
        error_msg = "RSS monitoring timeout"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("RSS Monitoring Timeout", error_msg, fk_task_run=fk_task_run)
        return False
        
    except Exception as e:
        error_msg = f"RSS monitoring error: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("RSS Monitoring Error", error_msg, fk_task_run=fk_task_run)
        return False

def process_pending_pdfs(cursor, fk_task_run):
    """Process any pending PDF downloads that may have failed"""
    if not ENABLE_BATCH_PDF_PROCESSING:
        log_message(cursor, fk_task_run, "INFO", "Batch PDF processing disabled")
        return True
    
    try:
        log_message(cursor, fk_task_run, "INFO", "Starting batch PDF processing for pending documents")
        
        # Find pending PDF downloads
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE c.fk_tool = 2  -- PACER
            AND d.rel_path = 'pending'
            AND d.date_created >= DATEADD(day, -7, GETDATE())  -- Last 7 days
        """)
        
        pending_count = cursor.fetchone()[0]
        
        if pending_count == 0:
            log_message(cursor, fk_task_run, "INFO", "No pending PDF downloads found")
            return True
        
        log_message(cursor, fk_task_run, "INFO", f"Found {pending_count} pending PDF downloads")
        
        # Run batch PDF processor
        result = subprocess.run(
            ["python", BATCH_PDF_PROCESSOR],
            cwd=r"u:\docketwatch\python",
            capture_output=True,
            text=True,
            timeout=PDF_PROCESSING_TIMEOUT
        )
        
        if result.returncode == 0:
            log_message(cursor, fk_task_run, "INFO", "Batch PDF processing completed successfully")
            return True
        else:
            error_msg = f"Batch PDF processing failed: {result.stderr}"
            log_message(cursor, fk_task_run, "WARNING", error_msg)
            return False
            
    except subprocess.TimeoutExpired:
        error_msg = "Batch PDF processing timeout"
        log_message(cursor, fk_task_run, "WARNING", error_msg)
        return False
        
    except Exception as e:
        error_msg = f"Batch PDF processing error: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("Batch PDF Processing Error", error_msg, fk_task_run=fk_task_run)
        return False

def retry_failed_pdfs(cursor, fk_task_run):
    """Retry failed PDF downloads using the direct downloader"""
    if not ENABLE_RETRY_FAILED_PDFS:
        log_message(cursor, fk_task_run, "INFO", "PDF retry disabled")
        return True
    
    try:
        log_message(cursor, fk_task_run, "INFO", "Starting retry of failed PDF downloads")
        
        # Find recent failed case events that need PDF retry
        cursor.execute("""
            SELECT ce.id, ce.event_no, c.case_name
            FROM docketwatch.dbo.case_events ce
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            LEFT JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_event
            WHERE c.fk_tool = 2  -- PACER
            AND ce.event_date >= DATEADD(day, -3, GETDATE())  -- Last 3 days
            AND (d.doc_uid IS NULL OR d.rel_path = 'pending')  -- No documents or pending
            AND ce.event_url IS NOT NULL
            ORDER BY ce.event_date DESC
        """)
        
        failed_events = cursor.fetchall()
        
        if not failed_events:
            log_message(cursor, fk_task_run, "INFO", "No failed PDF downloads to retry")
            return True
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(failed_events)} case events needing PDF retry")
        
        retry_count = 0
        success_count = 0
        
        for event_row in failed_events:
            case_event_id, event_no, case_name = event_row
            
            if retry_count >= 10:  # Limit retries per run
                log_message(cursor, fk_task_run, "INFO", "Reached retry limit for this run")
                break
            
            retry_count += 1
            
            try:
                log_message(cursor, fk_task_run, "INFO", 
                           f"Retrying PDF download for case event {case_event_id} ({case_name}, Event {event_no})")
                
                result = subprocess.run(
                    ["python", DIRECT_PDF_DOWNLOADER, str(case_event_id)],
                    cwd=r"u:\docketwatch\python",
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes per download
                )
                
                if result.returncode == 0:
                    success_count += 1
                    log_message(cursor, fk_task_run, "INFO", 
                               f"Successfully retried PDF download for case event {case_event_id}")
                else:
                    log_message(cursor, fk_task_run, "WARNING", 
                               f"PDF retry failed for case event {case_event_id}: {result.stderr}")
                
                # Small delay between retries
                time.sleep(2)
                
            except subprocess.TimeoutExpired:
                log_message(cursor, fk_task_run, "WARNING", 
                           f"PDF retry timeout for case event {case_event_id}")
            except Exception as retry_error:
                log_message(cursor, fk_task_run, "WARNING", 
                           f"PDF retry error for case event {case_event_id}: {retry_error}")
        
        log_message(cursor, fk_task_run, "INFO", 
                   f"PDF retry completed. Attempted: {retry_count}, Successful: {success_count}")
        
        return True
        
    except Exception as e:
        error_msg = f"PDF retry process error: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        error_notifier.log_error("PDF Retry Error", error_msg, fk_task_run=fk_task_run)
        return False

def generate_processing_summary(cursor, fk_task_run):
    """Generate and log a summary of processing results"""
    try:
        # Get processing statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_docs,
                SUM(CASE WHEN rel_path IS NOT NULL AND rel_path != 'pending' THEN 1 ELSE 0 END) as downloaded,
                SUM(CASE WHEN rel_path = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN summary_ai IS NOT NULL THEN 1 ELSE 0 END) as summarized
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE c.fk_tool = 2  -- PACER
            AND d.date_created >= DATEADD(day, -1, GETDATE())  -- Last 24 hours
        """)
        
        stats = cursor.fetchone()
        total_docs, downloaded, pending, summarized = stats
        
        summary_msg = f"""
        Processing Summary (Last 24 Hours):
        - Total documents: {total_docs}
        - Successfully downloaded: {downloaded}
        - Pending downloads: {pending}
        - AI summaries generated: {summarized}
        """
        
        log_message(cursor, fk_task_run, "INFO", summary_msg)
        
        return {
            'total_docs': total_docs,
            'downloaded': downloaded,
            'pending': pending,
            'summarized': summarized
        }
        
    except Exception as e:
        error_msg = f"Error generating processing summary: {e}"
        log_message(cursor, fk_task_run, "WARNING", error_msg)
        return {}

def main():
    """Main processing function"""
    print(f"Starting DocketWatch Complete RSS Processor at {datetime.now()}")
    print(f"Logging to: {LOG_FILE}")
    
    conn = None
    cursor = None
    fk_task_run = None
    
    try:
        # Setup database connection and task tracking
        conn, cursor, fk_task_run = setup_database_connection()
        
        log_message(cursor, fk_task_run, "INFO", "DocketWatch Complete RSS Processor started")
        
        # Step 1: Run RSS monitoring and processing
        rss_success = run_rss_monitoring(cursor, fk_task_run)
        
        # Step 2: Process any pending PDFs from previous runs
        batch_success = process_pending_pdfs(cursor, fk_task_run)
        
        # Step 3: Retry failed PDF downloads
        retry_success = retry_failed_pdfs(cursor, fk_task_run)
        
        # Step 4: Generate processing summary
        summary_stats = generate_processing_summary(cursor, fk_task_run)
        
        # Update task run status (simplified)
        overall_success = rss_success and batch_success and retry_success
        status = "Completed" if overall_success else "Completed with warnings"
        
        log_message(cursor, fk_task_run, "INFO", f"DocketWatch Complete RSS Processor finished: {status}")
        
        print(f"\nProcessing completed at {datetime.now()}")
        print(f"Status: {status}")
        if summary_stats:
            print(f"Documents processed in last 24h: {summary_stats.get('total_docs', 0)}")
            print(f"Successfully downloaded: {summary_stats.get('downloaded', 0)}")
            print(f"Pending downloads: {summary_stats.get('pending', 0)}")
            print(f"AI summaries generated: {summary_stats.get('summarized', 0)}")
        
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
            additional_context="Complete RSS processor main function failed"
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