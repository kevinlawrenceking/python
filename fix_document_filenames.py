"""
fix_document_filenames.py

This script scans the docs/cases/* directory structure to find PDF files that have
incorrect filenames using case_id instead of court case number. It renames files
from "E{case_id}.pdf" to "E{courtcasenumber}.pdf" pattern.

The script will:
1. Walk through all subdirectories in docs/cases/
2. For each PDF file found, check if it follows the pattern E{case_id}.pdf
3. If it does, rename it to E{courtcasenumber}.pdf using the case's court case number
4. Update the corresponding database record's rel_path if it exists

Usage:
    python fix_document_filenames.py [--dry-run] [--case-id CASE_ID]
    
    --dry-run: Show what would be renamed without actually renaming files
    --case-id: Only process files for a specific case ID
"""

import os
import sys
import argparse
import pyodbc
import re
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

def get_case_info(cursor, case_id):
    """
    Get case information including court case number.
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

def extract_case_id_from_filename(filename):
    """
    Extract case ID from filename if it follows pattern E{case_id}.pdf
    Returns case_id as integer or None if pattern doesn't match.
    """
    match = re.match(r'^E(\d+)\.pdf$', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def scan_case_directory(case_dir_path):
    """
    Scan a single case directory and return list of PDF files that need renaming.
    Returns list of tuples: (case_id, filename, full_path, needs_rename)
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
                    # Check if this file follows the E{case_id}.pdf pattern
                    extracted_case_id = extract_case_id_from_filename(filename)
                    needs_rename = extracted_case_id is not None and str(extracted_case_id) == case_id
                    
                    pdf_files.append((case_id, filename, full_path, needs_rename))
    except Exception as e:
        print(f"Error scanning directory {case_dir_path}: {e}")
    
    return pdf_files

def generate_new_filename(court_case_number):
    """
    Generate the new filename using court case number.
    Returns new filename in format E{courtcasenumber}.pdf
    """
    # Remove any spaces or special characters from court case number
    clean_case_number = re.sub(r'[^\w\-]', '', court_case_number)
    return f"E{clean_case_number}.pdf"

def update_document_record_path(cursor, case_id, old_filename, new_filename, dry_run=False):
    """
    Update the rel_path in the documents table for the renamed file.
    Returns True if updated, False otherwise.
    """
    old_rel_path = f"cases\\{case_id}\\{old_filename}"
    new_rel_path = f"cases\\{case_id}\\{new_filename}"
    
    if dry_run:
        # Check if there's a record to update
        cursor.execute("""
            SELECT COUNT(*) 
            FROM docketwatch.dbo.documents 
            WHERE fk_case = ? AND rel_path = ?
        """, (case_id, old_rel_path))
        
        if cursor.fetchone()[0] > 0:
            print(f"[DRY-RUN] Would update database record: {old_rel_path} → {new_rel_path}")
            return True
        else:
            return False
    
    try:
        cursor.execute("""
            UPDATE docketwatch.dbo.documents 
            SET rel_path = ?
            WHERE fk_case = ? AND rel_path = ?
        """, (new_rel_path, case_id, old_rel_path))
        
        # Check if any rows were updated
        if cursor.rowcount > 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error updating document record: {e}")
        return False

def rename_file(old_path, new_path, dry_run=False):
    """
    Rename a file from old_path to new_path.
    Returns True if successful, False otherwise.
    """
    if dry_run:
        print(f"[DRY-RUN] Would rename: {os.path.basename(old_path)} → {os.path.basename(new_path)}")
        return True
    
    try:
        # Check if target file already exists
        if os.path.exists(new_path):
            print(f"WARNING: Target file already exists: {new_path}")
            return False
        
        os.rename(old_path, new_path)
        return True
    except Exception as e:
        print(f"Error renaming file {old_path} to {new_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fix document filenames from E{case_id}.pdf to E{courtcasenumber}.pdf")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be renamed without actually renaming')
    parser.add_argument('--case-id', type=int, help='Only process files for specific case ID')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY-RUN MODE: No files will be renamed or database changes made")
        print("-" * 60)
    
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
    total_files_renamed = 0
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
        
        court_case_number = case_info['case_number']
        if not court_case_number:
            print(f"Warning: Case {case_id} has no court case number, skipping")
            continue
        
        # Scan for PDF files
        pdf_files = scan_case_directory(case_dir)
        files_needing_rename = [f for f in pdf_files if f[3]]  # f[3] is needs_rename
        
        total_files_found += len(pdf_files)
        
        if args.verbose and pdf_files:
            print(f"  Found {len(pdf_files)} PDF files, {len(files_needing_rename)} need renaming")
        
        # Process files that need renaming
        files_renamed_for_case = 0
        for case_id, filename, full_path, needs_rename in files_needing_rename:
            if not needs_rename:
                continue
            
            # Generate new filename
            new_filename = generate_new_filename(court_case_number)
            new_full_path = os.path.join(os.path.dirname(full_path), new_filename)
            
            # Check if target filename already exists
            if os.path.exists(new_full_path) and not args.dry_run:
                print(f"  SKIP: {filename} → {new_filename} (target file already exists)")
                continue
            
            # Rename the file
            if rename_file(full_path, new_full_path, args.dry_run):
                # Update database record if it exists
                db_updated = update_document_record_path(cursor, case_id, filename, new_filename, args.dry_run)
                
                files_renamed_for_case += 1
                total_files_renamed += 1
                
                if args.verbose:
                    action = "Would rename" if args.dry_run else "Renamed"
                    db_status = " (DB updated)" if db_updated else " (no DB record found)"
                    print(f"  {action}: {filename} → {new_filename}{db_status}")
            else:
                print(f"  ERROR: Failed to rename {filename}")
        
        if files_renamed_for_case > 0:
            print(f"Case {case_id} ({court_case_number}): {files_renamed_for_case} files renamed")
        
        cases_processed += 1
    
    # Commit database changes if not dry run
    if not args.dry_run and total_files_renamed > 0:
        try:
            conn.commit()
            print(f"\nCommitted database changes for {total_files_renamed} renamed files")
        except Exception as e:
            print(f"Error committing database changes: {e}")
            conn.rollback()
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Cases processed: {cases_processed}")
    print(f"Total PDF files found: {total_files_found}")
    print(f"Files renamed: {total_files_renamed}")
    
    if args.dry_run:
        print("\nThis was a dry run - no actual file renames or database changes were made")
        print("Run without --dry-run to actually rename the files and update database records")
    
    # Close database connection
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
