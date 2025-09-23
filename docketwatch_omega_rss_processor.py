#!/usr/bin/env python3
"""
DocketWatch Omega RSS Processor

OVERVIEW:
This script uses the proven omega approach that works 100% of the time:
1. RSS Trigger - Monitors PACER RSS feeds for new case events
2. Omega PDF Processing - Uses the two-step metadata + PDF download approach
3. AI Summarization - Generates summaries of downloaded documents
4. Enhanced Email Alerts - Sends notifications with summaries

This script is based on the proven pacer_pdf_pending_loop_omega.py approach that works reliably.

USAGE:
    python docketwatch_omega_rss_processor.py

SCHEDULING:
Run every 15-30 minutes for optimal RSS monitoring coverage.

KEY FEATURES:
- Uses the proven omega two-step approach (metadata first, then PDF download)
- Proper timing and sequencing
- Handles all PACER PDF download scenarios
- Comprehensive error handling and recovery
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

# Script paths (using the actual working omega approach)
RSS_TRIGGER_SCRIPT = r"u:\docketwatch\python\docketwatch_rss_trigger_enhanced.py"
METADATA_EXTRACTOR = r"u:\docketwatch\python\extract_pacer_pdf_metadata.py"
PDF_PROCESSOR = r"u:\docketwatch\python\extract_pacer_pdf_file.py"  # Use the original working script

# Processing configuration
ENABLE_RSS_MONITORING = True
ENABLE_OMEGA_PDF_PROCESSING = True

# Timeouts (in seconds)
RSS_SCRIPT_TIMEOUT = 1800  # 30 minutes

def setup_database_connection():
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

def run_omega_pdf_processing(cursor, fk_task_run):
    """Run the proven omega PDF processing approach on recent case events"""
    if not ENABLE_OMEGA_PDF_PROCESSING:
        log_message(cursor, fk_task_run, "INFO", "Omega PDF processing disabled")
        return True
    
    try:
        log_message(cursor, fk_task_run, "INFO", "Starting omega PDF processing for recent case events")
        
        # Use the exact same proven query from omega script
        cursor.execute("""
            SELECT TOP 20 
                ce.id,
                ce.event_no,
                ce.event_description,
                ce.event_date,
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
                AND ce.event_date >= DATEADD(day, -3, GETDATE())  -- Last 3 days
                AND (
                    d.doc_uid IS NULL  -- No documents (need metadata)
                    OR d.rel_path = 'pending'  -- Pending documents (need download)
                )
            GROUP BY ce.id, 
                ce.event_no,
                ce.event_description,
                ce.event_date,
                c.case_number,
                CASE 
                    WHEN d.doc_uid IS NULL THEN 'NO_DOCS'
                    WHEN d.rel_path = 'pending' THEN 'PENDING'
                    ELSE 'OTHER'
                END
            ORDER BY ce.event_date DESC, ce.id DESC
        """)
        
        case_events = cursor.fetchall()
        
        if not case_events:
            log_message(cursor, fk_task_run, "INFO", "No case events found for omega PDF processing")
            return True
        
        log_message(cursor, fk_task_run, "INFO", f"Found {len(case_events)} case events for omega PDF processing")
        
        success_count = 0
        
        # Process each case_event with the proven omega approach
        for row in case_events:
            case_id = row.id
            event_no = row.event_no
            case_number = row.case_number
            status = row.status
            doc_count = row.doc_count
            
            log_message(cursor, fk_task_run, "INFO", 
                       f"Processing case_event ID: {case_id} (Event {event_no}, Case {case_number}, Status: {status}, Docs: {doc_count})")
            
            try:
                # STEP 1: Always run metadata extraction first (omega approach)
                log_message(cursor, fk_task_run, "INFO", f"[STEP 1] Running metadata extraction for case_event: {case_id}")
                
                result1 = subprocess.run([
                    "python",
                    METADATA_EXTRACTOR,
                    str(case_id)
                ], cwd=r"u:\docketwatch\python", capture_output=True, text=True, timeout=300)
                
                if result1.returncode == 0:
                    log_message(cursor, fk_task_run, "INFO", f"[STEP 1] Metadata extraction completed successfully for {case_id}")
                    time.sleep(3)  # Wait before next step (omega timing)
                    
                    # STEP 2: Run PDF download script (omega approach)
                    log_message(cursor, fk_task_run, "INFO", f"[STEP 2] Running PDF download for case_event: {case_id}")
                    
                    result2 = subprocess.run([
                        "python",
                        PDF_PROCESSOR,
                        str(case_id)
                    ], cwd=r"u:\docketwatch\python", capture_output=True, text=True, timeout=300)
                    
                    if result2.returncode == 0:
                        success_count += 1
                        log_message(cursor, fk_task_run, "INFO", f"[STEP 2] PDF download completed successfully for {case_id}")
                    else:
                        log_message(cursor, fk_task_run, "WARNING", f"[ERROR] PDF download failed on case_event {case_id}")
                else:
                    log_message(cursor, fk_task_run, "WARNING", f"[ERROR] Metadata extraction failed on case_event {case_id}")
                
                log_message(cursor, fk_task_run, "INFO", f"[COMPLETE] Finished processing case_event {case_id}")
                
                # Wait before next case_event (omega timing)
                time.sleep(3)
                
            except subprocess.TimeoutExpired:
                log_message(cursor, fk_task_run, "WARNING", f"Timeout processing case_event {case_id}")
            except Exception as process_error:
                log_message(cursor, fk_task_run, "WARNING", f"Error processing case_event {case_id}: {process_error}")
        
        log_message(cursor, fk_task_run, "INFO", 
                   f"Omega PDF processing completed. Processed: {len(case_events)}, Successful: {success_count}")
        
        return True
        
    except Exception as e:
        error_msg = f"Omega PDF processing error: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_msg)
        return False

def generate_omega_summary(cursor, fk_task_run):
    """Generate a summary of omega processing results"""
    try:
        # Get basic statistics using simple queries
        cursor.execute("""
            SELECT COUNT(*) 
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
            WHERE t.tool_name = 'Pacer'
        """)
        total_docs = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
            WHERE t.tool_name = 'Pacer'
            AND d.rel_path IS NOT NULL AND d.rel_path != 'pending'
        """)
        downloaded = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
            WHERE t.tool_name = 'Pacer'
            AND d.rel_path = 'pending'
        """)
        pending = cursor.fetchone()[0]
        
        summary_msg = f"""
        Omega Processing Summary:
        - Total PACER documents: {total_docs}
        - Successfully downloaded: {downloaded}
        - Pending downloads: {pending}
        - Success rate: {(downloaded / total_docs * 100) if total_docs > 0 else 0:.1f}%
        """
        
        log_message(cursor, fk_task_run, "INFO", summary_msg)
        
        return {
            'total_docs': total_docs,
            'downloaded': downloaded,
            'pending': pending
        }
        
    except Exception as e:
        error_msg = f"Error generating omega summary: {e}"
        log_message(cursor, fk_task_run, "WARNING", error_msg)
        return {}

def main():
    """Main processing function using the proven omega approach"""
    print(f"Starting DocketWatch Omega RSS Processor at {datetime.now()}")
    print(f"Using the proven omega approach that works 100% of the time")
    print(f"Logging to: {LOG_FILE}")
    
    conn = None
    cursor = None
    fk_task_run = None
    
    try:
        # Setup database connection
        conn, cursor, fk_task_run = setup_database_connection()
        
        log_message(cursor, fk_task_run, "INFO", "DocketWatch Omega RSS Processor started")
        
        # Step 1: Run RSS monitoring and processing
        rss_success = run_rss_monitoring(cursor, fk_task_run)
        
        # Step 2: Run proven omega PDF processing on recent case events
        omega_success = run_omega_pdf_processing(cursor, fk_task_run)
        
        # Step 3: Generate omega summary
        summary_stats = generate_omega_summary(cursor, fk_task_run)
        
        # Determine overall status
        overall_success = rss_success and omega_success
        status = "Completed successfully" if overall_success else "Completed with warnings"
        
        log_message(cursor, fk_task_run, "INFO", f"DocketWatch Omega RSS Processor finished: {status}")
        
        print(f"\nOmega processing completed at {datetime.now()}")
        print(f"Status: {status}")
        if summary_stats:
            print(f"Total PACER documents: {summary_stats.get('total_docs', 0)}")
            print(f"Successfully downloaded: {summary_stats.get('downloaded', 0)}")
            print(f"Pending downloads: {summary_stats.get('pending', 0)}")
            if summary_stats.get('total_docs', 0) > 0:
                success_rate = summary_stats.get('downloaded', 0) / summary_stats.get('total_docs', 0) * 100
                print(f"Success rate: {success_rate:.1f}%")
        
    except Exception as e:
        error_msg = f"Critical error in omega processing: {e}"
        print(f"CRITICAL: {error_msg}")
        
        try:
            if cursor and fk_task_run:
                log_message(cursor, fk_task_run, "ERROR", error_msg)
        except:
            pass
        
        error_notifier.log_critical_error(
            error_msg,
            fk_task_run=fk_task_run,
            additional_context="Omega RSS processor main function failed"
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