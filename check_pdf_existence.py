#!/usr/bin/env python3
"""
PDF Document Existence Checker

This script loops through documents in the database and checks if the corresponding
PDF files actually exist on the file system. If a document is marked as downloaded
but the file doesn't exist, it updates the status to 'Missing'.

WORKFLOW:
1. Query for documents that have rel_path set (supposed to be downloaded)
2. Check if the actual file exists at the specified path
3. Update status to 'Missing' if file doesn't exist
4. Optionally reset download status to allow re-downloading

USAGE:
- Run with no arguments to check all documents
- Use --case-id to check specific case
- Use --case-event-id to check specific case event
- Use --reset-missing to reset missing files for re-download
"""

import sys
import os
import argparse
import pyodbc
import time
from pathlib import Path

# PDF storage location
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs"

def log_message(message):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

def check_file_exists(rel_path, fk_case):
    """Check if a PDF file exists at the expected location"""
    if not rel_path:
        return False, "No relative path specified"
    
    try:
        # Construct full path - rel_path already includes cases/case_id/filename
        full_path = os.path.join(FINAL_PDF_DIR, rel_path)
        
        # Normalize path separators
        full_path = os.path.normpath(full_path)
        
        exists = os.path.exists(full_path)
        
        if exists:
            # Check if it's actually a file and has content
            if os.path.isfile(full_path):
                file_size = os.path.getsize(full_path)
                if file_size > 0:
                    return True, f"File exists ({file_size} bytes)"
                else:
                    return False, "File exists but is empty (0 bytes)"
            else:
                return False, "Path exists but is not a file"
        else:
            return False, "File does not exist"
    
    except Exception as e:
        return False, f"Error checking file: {str(e)}"

def update_document_status(cursor, doc_uid, status):
    """Update document status in database"""
    try:
        cursor.execute("""
            UPDATE docketwatch.dbo.documents 
            SET status = ?
            WHERE doc_uid = ?
        """, (status, doc_uid))
        
        return True
    except Exception as e:
        log_message(f"❌ Error updating document {doc_uid}: {e}")
        return False

def reset_missing_document(cursor, doc_uid):
    """Reset a missing document for re-download"""
    try:
        cursor.execute("""
            UPDATE docketwatch.dbo.documents 
            SET status = NULL, 
                rel_path = NULL, 
                date_downloaded = NULL
            WHERE doc_uid = ?
        """, (doc_uid,))
        
        return True
    except Exception as e:
        log_message(f"❌ Error resetting document {doc_uid}: {e}")
        return False

def build_query(case_id=None, case_event_id=None):
    """Build the appropriate query based on filters"""
    
    base_query = """
        SELECT 
            d.doc_uid,
            d.doc_id,
            d.pdf_no,
            d.rel_path,
            d.date_downloaded,
            d.status,
            d.fk_case,
            d.fk_case_event,
            c.case_name,
            ce.event_no,
            ce.event_description
        FROM docketwatch.dbo.documents d
        LEFT JOIN docketwatch.dbo.cases c ON d.fk_case = c.case_id
        LEFT JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.case_event_id
        WHERE d.rel_path IS NOT NULL 
        AND d.date_downloaded IS NOT NULL
    """
    
    params = []
    
    if case_event_id:
        base_query += " AND d.fk_case_event = ?"
        params.append(case_event_id)
    elif case_id:
        base_query += " AND d.fk_case = ?"
        params.append(case_id)
    
    base_query += " ORDER BY d.fk_case, d.doc_id"
    
    return base_query, params

def check_documents(case_id=None, case_event_id=None, reset_missing=False, limit=None):
    """Main function to check document existence"""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        log_message("🔍 PDF DOCUMENT EXISTENCE CHECKER")
        log_message("=" * 50)
        
        if case_event_id:
            log_message(f"Checking documents for case event: {case_event_id}")
        elif case_id:
            log_message(f"Checking documents for case: {case_id}")
        else:
            log_message("Checking ALL documents with download records")
        
        if reset_missing:
            log_message("⚠️  RESET MODE: Missing files will be reset for re-download")
        
        log_message(f"PDF Directory: {FINAL_PDF_DIR}")
        log_message("=" * 50)
        
        # Build and execute query
        query, params = build_query(case_id, case_event_id)
        
        if limit:
            query += f" TOP {limit}"
        
        cursor.execute(query, params)
        documents = cursor.fetchall()
        
        if not documents:
            log_message("📭 No documents found matching criteria")
            return
        
        log_message(f"📄 Found {len(documents)} documents to check")
        log_message("-" * 50)
        
        # Counters
        total_checked = 0
        files_exist = 0
        files_missing = 0
        files_updated = 0
        files_reset = 0
        
        for doc in documents:
            (doc_uid, doc_id, pdf_no, rel_path, date_downloaded, status, 
             fk_case, fk_case_event, case_name, event_no, event_description) = doc
            
            total_checked += 1
            
            # Check if file exists
            exists, check_message = check_file_exists(rel_path, fk_case)
            
            case_display = case_name[:50] + "..." if case_name and len(case_name) > 50 else case_name
            
            log_message(f"\n📄 Document {doc_id} (PDF #{pdf_no})")
            log_message(f"   Case: {case_display}")
            log_message(f"   Event: {event_no} - {event_description[:50]}..." if event_description and len(event_description) > 50 else f"   Event: {event_no} - {event_description}")
            log_message(f"   Path: {rel_path}")
            log_message(f"   Downloaded: {date_downloaded}")
            log_message(f"   Current Status: {status}")
            
            if exists:
                log_message(f"   ✅ {check_message}")
                files_exist += 1
            else:
                log_message(f"   ❌ {check_message}")
                files_missing += 1
                
                if reset_missing:
                    # Reset the document for re-download
                    if reset_missing_document(cursor, doc_uid):
                        log_message(f"   🔄 Document reset for re-download")
                        files_reset += 1
                    else:
                        log_message(f"   ❌ Failed to reset document")
                else:
                    # Update status to Missing
                    if update_document_status(cursor, doc_uid, 'Missing'):
                        log_message(f"   📝 Status updated to 'Missing'")
                        files_updated += 1
                    else:
                        log_message(f"   ❌ Failed to update status")
        
        # Commit changes
        conn.commit()
        
        # Summary
        log_message("\n" + "=" * 50)
        log_message("📊 SUMMARY:")
        log_message(f"   📄 Total documents checked: {total_checked}")
        log_message(f"   ✅ Files exist: {files_exist}")
        log_message(f"   ❌ Files missing: {files_missing}")
        
        if reset_missing:
            log_message(f"   🔄 Documents reset: {files_reset}")
        else:
            log_message(f"   📝 Statuses updated: {files_updated}")
        
        if files_missing > 0:
            log_message(f"\n💡 To reset missing files for re-download:")
            log_message(f"   python {os.path.basename(__file__)} --reset-missing")
        
        log_message("=" * 50)
        
    except Exception as e:
        log_message(f"❌ Error checking documents: {e}")
        return False
    
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Check PDF document existence on file system")
    parser.add_argument("--case-id", type=str, help="Check documents for specific case ID")
    parser.add_argument("--case-event-id", type=str, help="Check documents for specific case event ID")
    parser.add_argument("--reset-missing", action="store_true", help="Reset missing files for re-download")
    parser.add_argument("--limit", type=int, help="Limit number of documents to check (for testing)")
    
    args = parser.parse_args()
    
    if args.case_id and args.case_event_id:
        print("❌ Error: Cannot specify both --case-id and --case-event-id")
        sys.exit(1)
    
    success = check_documents(
        case_id=args.case_id,
        case_event_id=args.case_event_id,
        reset_missing=args.reset_missing,
        limit=args.limit
    )
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
