"""
Workflow Manager for DocketWatch
===============================

This module orchestrates complete workflows by combining the modular components.
It provides high-level workflow operations that can be called from production scripts.

Example workflows:
- Complete PDF processing (download → OCR → summarize → alert)
- Case event processing (scrape → update → organize)
- Batch processing operations
"""

import logging
import time
from datetime import datetime

# Import our modular components
from core.pdf_operations import (
    perform_ocr_for_documents, 
    get_pdf_processing_stats,
    extract_text_from_pdf
)
from core.case_event_manager import (
    insert_new_case_events,
    create_case_update_if_needed,
    update_case_records,
    mark_case_found,
    mark_case_not_found,
    log_case_message
)

class DocketWatchWorkflow:
    """
    Main workflow orchestrator for DocketWatch operations.
    """
    
    def __init__(self, cursor, docs_root_dir=r"\\10.146.176.84\general\docketwatch\docs", fk_task_run=None):
        """
        Initialize the workflow manager.
        
        Args:
            cursor: Database cursor
            docs_root_dir: Root directory for document storage
            fk_task_run: Optional task run ID for logging
        """
        self.cursor = cursor
        self.docs_root_dir = docs_root_dir
        self.fk_task_run = fk_task_run
        
    def process_case_event_complete(self, case_event_id):
        """
        Complete workflow for a case event: OCR → summarize → create updates → alerts.
        
        Args:
            case_event_id: ID of the case event to process
            
        Returns:
            dict: Results summary
        """
        results = {
            'case_event_id': case_event_id,
            'ocr_processed': 0,
            'summaries_generated': 0,
            'case_update_created': False,
            'alerts_sent': 0,
            'errors': []
        }
        
        try:
            # Step 1: OCR Processing
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Starting complete workflow for case_event {case_event_id}")
            
            ocr_count = perform_ocr_for_documents(self.cursor, case_event_id, self.docs_root_dir)
            results['ocr_processed'] = ocr_count
            
            if ocr_count > 0:
                log_case_message(self.cursor, self.fk_task_run, "INFO", 
                               f"OCR completed for {ocr_count} documents")
            
            # Step 2: AI Summarization (would import from ai_summarizer module)
            # summary_count = generate_ai_summaries_for_event(self.cursor, case_event_id)
            # results['summaries_generated'] = summary_count
            
            # Step 3: Create case update if needed
            case_id = self._get_case_id_for_event(case_event_id)
            if case_id:
                update_id, event_ids = create_case_update_if_needed(self.cursor, case_id)
                if update_id:
                    results['case_update_created'] = True
                    log_case_message(self.cursor, self.fk_task_run, "INFO", 
                                   f"Created case_update {update_id} with {len(event_ids)} events")
            
            # Step 4: Send alerts if storyworthy (would be in alert_system module)
            # alert_count = process_storyworthy_alerts(self.cursor, case_id)
            # results['alerts_sent'] = alert_count
            
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Complete workflow finished for case_event {case_event_id}")
            
        except Exception as e:
            error_msg = f"Workflow failed for case_event {case_event_id}: {e}"
            results['errors'].append(error_msg)
            log_case_message(self.cursor, self.fk_task_run, "ERROR", error_msg)
            logging.error(error_msg)
        
        return results
    
    def process_pdf_workflow_only(self, case_event_id):
        """
        PDF-only workflow: download → OCR → update metadata.
        
        Args:
            case_event_id: ID of the case event to process
            
        Returns:
            dict: Results summary
        """
        results = {
            'case_event_id': case_event_id,
            'pdfs_downloaded': 0,
            'ocr_processed': 0,
            'errors': []
        }
        
        try:
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Starting PDF workflow for case_event {case_event_id}")
            
            # Step 1: Download pending PDFs (would be in pdf_operations)
            # download_count = download_pending_pdfs_for_event(self.cursor, case_event_id)
            # results['pdfs_downloaded'] = download_count
            
            # Step 2: OCR Processing
            ocr_count = perform_ocr_for_documents(self.cursor, case_event_id, self.docs_root_dir)
            results['ocr_processed'] = ocr_count
            
            # Step 3: Update document metadata
            stats = get_pdf_processing_stats(self.cursor, case_event_id)
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"PDF workflow complete. Stats: {stats}")
            
        except Exception as e:
            error_msg = f"PDF workflow failed for case_event {case_event_id}: {e}"
            results['errors'].append(error_msg)
            log_case_message(self.cursor, self.fk_task_run, "ERROR", error_msg)
        
        return results
    
    def process_case_scraping_workflow(self, case_id, case_data, tool_id):
        """
        Case scraping workflow: update case → insert events → mark status.
        
        Args:
            case_id: Case ID
            case_data: Dictionary with case information
            tool_id: ID of the tool performing the scraping
            
        Returns:
            dict: Results summary
        """
        results = {
            'case_id': case_id,
            'case_updated': False,
            'events_inserted': 0,
            'status_updated': False,
            'errors': []
        }
        
        try:
            # Step 1: Update case record
            success = update_case_records(
                self.cursor, case_id, 
                case_data.get('case_number'),
                case_data.get('case_name'),
                tool_id,
                case_data.get('fk_court'),
                case_data.get('case_type'),
                self.fk_task_run,
                case_data.get('case_url')
            )
            results['case_updated'] = success
            
            # Step 2: Insert new events
            if 'events' in case_data and case_data['events']:
                event_count = insert_new_case_events(
                    self.cursor, case_id, case_data['events'], self.fk_task_run
                )
                results['events_inserted'] = event_count
            
            # Step 3: Mark case as found (reset not_found status)
            mark_case_found(self.cursor, case_id)
            results['status_updated'] = True
            
            log_case_message(self.cursor, self.fk_task_run, "INFO", 
                           f"Scraping workflow complete for case {case_id}: "
                           f"{results['events_inserted']} new events")
            
        except Exception as e:
            error_msg = f"Scraping workflow failed for case {case_id}: {e}"
            results['errors'].append(error_msg)
            log_case_message(self.cursor, self.fk_task_run, "ERROR", error_msg)
            
            # Mark case as not found if scraping fails
            mark_case_not_found(self.cursor, case_id, self.fk_task_run)
        
        return results
    
    def _get_case_id_for_event(self, case_event_id):
        """Get the case ID for a given case event."""
        self.cursor.execute("""
            SELECT fk_cases FROM docketwatch.dbo.case_events 
            WHERE id = ?
        """, (case_event_id,))
        row = self.cursor.fetchone()
        return row.fk_cases if row else None

class BatchProcessor:
    """
    Handles batch processing operations for multiple cases/events.
    """
    
    def __init__(self, cursor, docs_root_dir=r"\\10.146.176.84\general\docketwatch\docs"):
        """
        Initialize the batch processor.
        
        Args:
            cursor: Database cursor
            docs_root_dir: Root directory for document storage
        """
        self.cursor = cursor
        self.docs_root_dir = docs_root_dir
        self.workflow = DocketWatchWorkflow(cursor, docs_root_dir)
    
    def process_pending_pdfs(self, limit=100):
        """
        Batch process all case events that need PDF processing.
        
        Args:
            limit: Maximum number of case events to process
            
        Returns:
            dict: Processing summary
        """
        # Get case events that need PDF processing
        self.cursor.execute(f"""
            SELECT TOP {limit} e.id
            FROM docketwatch.dbo.case_events e
            WHERE e.event_url IS NOT NULL
              AND e.id NOT IN (
                  SELECT DISTINCT fk_case_event
                  FROM docketwatch.dbo.documents
                  WHERE fk_case_event IS NOT NULL
              )
            ORDER BY e.created_at DESC
        """)
        
        case_event_ids = [row.id for row in self.cursor.fetchall()]
        
        summary = {
            'total_events': len(case_event_ids),
            'processed': 0,
            'failed': 0,
            'total_pdfs_processed': 0,
            'start_time': datetime.now()
        }
        
        logging.info(f"Starting batch PDF processing for {len(case_event_ids)} case events")
        
        for i, case_event_id in enumerate(case_event_ids):
            try:
                logging.info(f"[{i+1}/{len(case_event_ids)}] Processing case_event {case_event_id}")
                
                # Use the complete workflow for each event
                result = self.workflow.process_pdf_workflow_only(case_event_id)
                
                if result['errors']:
                    summary['failed'] += 1
                    logging.warning(f"Case event {case_event_id} had errors: {result['errors']}")
                else:
                    summary['processed'] += 1
                    summary['total_pdfs_processed'] += result['ocr_processed']
                
                # Small delay to avoid overwhelming the system
                time.sleep(1)
                
            except Exception as e:
                summary['failed'] += 1
                logging.error(f"Failed to process case_event {case_event_id}: {e}")
        
        summary['end_time'] = datetime.now()
        summary['duration'] = summary['end_time'] - summary['start_time']
        
        logging.info(f"Batch PDF processing complete: {summary['processed']} processed, "
                    f"{summary['failed']} failed, {summary['total_pdfs_processed']} PDFs processed")
        
        return summary
    
    def process_pending_ocr(self, limit=50):
        """
        Batch process documents that need OCR.
        
        Args:
            limit: Maximum number of documents to process
            
        Returns:
            dict: Processing summary
        """
        # Get documents that need OCR
        self.cursor.execute(f"""
            SELECT TOP {limit} 
                d.fk_case_event,
                COUNT(*) as doc_count
            FROM docketwatch.dbo.documents d
            WHERE (d.ocr_text IS NULL OR LEN(d.ocr_text) < 10)
              AND d.rel_path IS NOT NULL 
              AND d.rel_path NOT IN ('pending', '')
            GROUP BY d.fk_case_event
            ORDER BY doc_count DESC
        """)
        
        case_events = cursor.fetchall()
        
        summary = {
            'total_case_events': len(case_events),
            'documents_processed': 0,
            'failed_events': 0,
            'start_time': datetime.now()
        }
        
        for case_event_id, doc_count in case_events:
            try:
                processed = perform_ocr_for_documents(self.cursor, case_event_id, self.docs_root_dir)
                summary['documents_processed'] += processed
                logging.info(f"OCR processed {processed} documents for case_event {case_event_id}")
                
            except Exception as e:
                summary['failed_events'] += 1
                logging.error(f"OCR failed for case_event {case_event_id}: {e}")
        
        summary['end_time'] = datetime.now()
        return summary

# === Convenience Functions ===

def create_workflow_for_case_event(cursor, case_event_id, fk_task_run=None):
    """
    Convenience function to create a workflow for a specific case event.
    
    Args:
        cursor: Database cursor
        case_event_id: Case event ID
        fk_task_run: Optional task run ID
        
    Returns:
        DocketWatchWorkflow: Configured workflow instance
    """
    return DocketWatchWorkflow(cursor, fk_task_run=fk_task_run)

def run_complete_pdf_workflow(cursor, case_event_id, fk_task_run=None):
    """
    Convenience function to run the complete PDF workflow for a case event.
    
    Args:
        cursor: Database cursor
        case_event_id: Case event ID
        fk_task_run: Optional task run ID
        
    Returns:
        dict: Workflow results
    """
    workflow = DocketWatchWorkflow(cursor, fk_task_run=fk_task_run)
    return workflow.process_case_event_complete(case_event_id)

def run_batch_pdf_processing(cursor, limit=100):
    """
    Convenience function to run batch PDF processing.
    
    Args:
        cursor: Database cursor
        limit: Maximum number of case events to process
        
    Returns:
        dict: Processing summary
    """
    processor = BatchProcessor(cursor)
    return processor.process_pending_pdfs(limit)

# === Example Usage ===

if __name__ == "__main__":
    # Example of how to use the workflow manager
    import pyodbc
    
    # Database connection
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    try:
        # Example 1: Process a specific case event
        case_event_id = "E39D680E-8618-4C32-8866-19829CF57D41"
        workflow = DocketWatchWorkflow(cursor)
        result = workflow.process_case_event_complete(case_event_id)
        print(f"Workflow result: {result}")
        
        # Example 2: Batch process pending PDFs
        batch_processor = BatchProcessor(cursor)
        summary = batch_processor.process_pending_pdfs(limit=10)
        print(f"Batch processing summary: {summary}")
        
    finally:
        cursor.close()
        conn.close()
