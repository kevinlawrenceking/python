"""
create_missing_document_records.py

This script scans the docs/cases/* directory structure to find PDF files that exist
on disk but don't have corresponding records in the documents table. For each missing
document, it creates a new record in the database.

The script will:
1. Walk through all subdirectories in docs/cases/
2. For each PDF file found, check if there's a corresponding document record
3. Create database records for any missing documents
4. Associate documents with cases based on the directory structure

Usage:
    python create_missing_document_records.py [--dry-run] [--case-id CASE_ID]
    
    --dry-run: Show what would be created without actually inserting records
    --case-id: Only process files for a specific case ID
"""

import os
import sys
import argparse
import pyodbc
import uuid
from datetime import datetime
from pathlib import Path

# Configuration
DOCS_ROOT = r"\\10.146.176.84\general\docketwatch\docs\cases"
DSN = "Docketwatch"

def get_db_connection():
    """Get database connection and cursor."""
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    cursor = conn.cursor()
    return conn, cursor

def scan_case_directory(case_dir_path):
    """
    Scan a single case directory and return list of PDF files.
    Returns list of tuples: (case_id, filename, full_path, file_size, date_modified)
    """
    case_id = os.path.basename(case_dir_path)
    pdf_files = []
    
    if not os.path.exists(case_dir_path):
        return pdf_files
    
    try:
        for filename in os.listdir(case_dir_path):
            if filename.lower().endswith('.pdf'):
                full_path = os.path.join(case_dir_path, filename)
                if os.path.isfile(full_path):
                    file_size = os.path.getsize(full_path)
                    date_modified = datetime.fromtimestamp(os.path.getmtime(full_path))
                    pdf_files.append((case_id, filename, full_path, file_size, date_modified))
    except Exception as e:
        print(f"Error scanning directory {case_dir_path}: {e}")
    
    return pdf_files

def check_document_exists(cursor, case_id, filename):
    """
    Check if a document record already exists for this case and filename.
    Returns True if exists, False otherwise.
    """
    # First check by doc_id if filename follows E{doc_id}.pdf pattern
    doc_id = extract_doc_id_from_filename(filename)
    if doc_id is not None:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM docketwatch.dbo.documents 
            WHERE fk_case = ? AND doc_id = ?
        """, (case_id, doc_id))
        
        if cursor.fetchone()[0] > 0:
            return True
    
    # Also check by rel_path for files that don't follow the pattern
    rel_path = f"cases\\{case_id}\\{filename}"
    cursor.execute("""
        SELECT COUNT(*) 
        FROM docketwatch.dbo.documents 
        WHERE fk_case = ? AND rel_path = ?
    """, (case_id, rel_path))
    
    count = cursor.fetchone()[0]
    return count > 0

def extract_doc_id_from_filename(filename):
    """
    Extract document ID from filename if it follows pattern E{doc_id}.pdf
    Returns doc_id as integer or None if pattern doesn't match.
    """
    import re
    match = re.match(r'^E(\d+)\.pdf$', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def get_case_info(cursor, case_id):
    """
    Get basic case information to help determine tool_id.
    Returns dict with case info or None if case doesn't exist.
    """
    cursor.execute("""
        SELECT id, case_number, case_name, fk_tool, status
        FROM docketwatch.dbo.cases
        WHERE id = ?
    """, (case_id,))
    
    row = cursor.fetchone()
    if row:
        return {
            'id': row.id,
            'case_number': row.case_number,
            'case_name': row.case_name,
            'fk_tool': row.fk_tool,
            'status': row.status
        }
    return None

def create_document_record(cursor, case_id, filename, file_size, date_modified, tool_id=None, dry_run=False):
    """
    Create a new document record in the database.
    Returns the doc_uid if successful, None otherwise.
    """
    if dry_run:
        print(f"[DRY-RUN] Would create document record for case {case_id}, file {filename}")
        return "dry-run-uuid"
    
    doc_uid = str(uuid.uuid4())
    doc_id = extract_doc_id_from_filename(filename)
    rel_path = f"cases\\{case_id}\\{filename}"
    
    # Default tool_id to 2 (PACER) if not specified
    if tool_id is None:
        tool_id = 2
    
    try:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.documents (
                doc_uid, fk_case, fk_tool, doc_id, rel_path, 
                file_size, date_downloaded, pdf_title, pdf_type, pdf_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_uid, case_id, tool_id, doc_id, rel_path,
            file_size, date_modified, filename, 'Document', 0
        ))
        
        return doc_uid
    except Exception as e:
        print(f"Error creating document record for {filename}: {e}")
        return None

def update_pending_document(cursor, case_id, filename, file_size, date_modified, dry_run=False):
    """
    Update an existing document record that has rel_path = 'pending' with the correct path.
    Returns True if updated, False otherwise.
    """
    doc_id = extract_doc_id_from_filename(filename)
    if doc_id is None:
        return False
    
    if dry_run:
        print(f"[DRY-RUN] Would update pending document record for case {case_id}, file {filename}")
        return True
    
    rel_path = f"cases\\{case_id}\\{filename}"
    
    try:
        cursor.execute("""
            UPDATE docketwatch.dbo.documents 
            SET rel_path = ?, file_size = ?, date_downloaded = ?
            WHERE fk_case = ? AND doc_id = ? AND rel_path = 'pending'
        """, (rel_path, file_size, date_modified, case_id, doc_id))
        
        # Check if any rows were updated
        if cursor.rowcount > 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error updating pending document record for {filename}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Create missing document records from files in docs/cases/*")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created without actually inserting')
    parser.add_argument('--case-id', type=int, help='Only process files for specific case ID')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY-RUN MODE: No database changes will be made")
        print("-" * 50)
    
    # Get database connection
    try:
        conn, cursor = get_db_connection()
        print(f"Connected to database: {DSN}")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)
    
    # Determine which case directories to process
    case_dirs_to_process = []
    
    if args.case_id:
        # Process only specific case
        case_dir = os.path.join(DOCS_ROOT, str(args.case_id))
        if os.path.exists(case_dir):
            case_dirs_to_process.append(case_dir)
        else:
            print(f"Case directory not found: {case_dir}")
            sys.exit(1)
    else:
        # Process all case directories
        if not os.path.exists(DOCS_ROOT):
            print(f"Root directory not found: {DOCS_ROOT}")
            sys.exit(1)
        
        for item in os.listdir(DOCS_ROOT):
            case_dir = os.path.join(DOCS_ROOT, item)
            if os.path.isdir(case_dir) and item.isdigit():
                case_dirs_to_process.append(case_dir)
    
    print(f"Found {len(case_dirs_to_process)} case directories to process")
    
    # Process each case directory
    total_files_found = 0
    total_records_created = 0
    cases_processed = 0
    
    for case_dir in case_dirs_to_process:
        case_id = os.path.basename(case_dir)
        
        if args.verbose:
            print(f"\nProcessing case directory: {case_id}")
        
        # Get case info from database
        case_info = get_case_info(cursor, case_id)
        if not case_info:
            print(f"Warning: Case {case_id} not found in database, skipping directory")
            continue
        
        # Scan for PDF files
        pdf_files = scan_case_directory(case_dir)
        total_files_found += len(pdf_files)
        
        if args.verbose and pdf_files:
            print(f"  Found {len(pdf_files)} PDF files")
        
        # Check each PDF file
        files_created_for_case = 0
        files_updated_for_case = 0
        for case_id, filename, full_path, file_size, date_modified in pdf_files:
            # Check if document record already exists
            if check_document_exists(cursor, case_id, filename):
                if args.verbose:
                    print(f"  SKIP: {filename} (record already exists)")
                continue
            
            # Try to update existing pending document first
            if update_pending_document(cursor, case_id, filename, file_size, date_modified, args.dry_run):
                files_updated_for_case += 1
                total_records_created += 1
                if args.verbose:
                    action = "Would update" if args.dry_run else "Updated"
                    print(f"  {action}: {filename} (pending → full path)")
            else:
                # Create new document record
                doc_uid = create_document_record(
                    cursor, case_id, filename, file_size, date_modified, 
                    case_info['fk_tool'], args.dry_run
                )
                
                if doc_uid:
                    files_created_for_case += 1
                    total_records_created += 1
                    if args.verbose:
                        action = "Would create" if args.dry_run else "Created"
                        print(f"  {action}: {filename} (size: {file_size:,} bytes)")
        
        if files_created_for_case > 0 or files_updated_for_case > 0:
            print(f"Case {case_id} ({case_info['case_number']}): {files_created_for_case} records created, {files_updated_for_case} records updated")
        
        cases_processed += 1
    
    # Commit changes if not dry run
    if not args.dry_run and total_records_created > 0:
        try:
            conn.commit()
            print(f"\nCommitted {total_records_created} document record changes to database")
        except Exception as e:
            print(f"Error committing changes: {e}")
            conn.rollback()
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Cases processed: {cases_processed}")
    print(f"Total PDF files found: {total_files_found}")
    print(f"Document records created/updated: {total_records_created}")
    
    if args.dry_run:
        print("\nThis was a dry run - no actual database changes were made")
        print("Run without --dry-run to actually create/update the records")
    
    # Close database connection
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
