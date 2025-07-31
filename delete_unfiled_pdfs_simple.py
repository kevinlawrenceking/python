#!/usr/bin/env python3
"""
Delete Unfiled PDFs Script - Simple Version
===========================================
This script deletes PDF files for unfiled cases with "Removed" status.
It processes 10 files at a time and prints what was deleted.

Usage: python delete_unfiled_pdfs_simple.py [server_name]
"""

import pyodbc
import os
import sys
from pathlib import Path

# Database connection settings
DB_DSN = "Docketwatch"  # DSN name

# Base file path
BASE_PATH = r"\\10.146.176.84\general\DOCKETWATCH\docs"

def get_db_connection():
    """Create database connection using DSN (same as your other scripts)"""
    try:
        conn_str = f"DSN={DB_DSN};TrustServerCertificate=yes;"
        conn = pyodbc.connect(conn_str)
        print(f"Connected to database using DSN: {DB_DSN}")
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        print(f"Make sure the DSN '{DB_DSN}' is configured on this system")
        return None

def main():
    print("Unfiled PDF Deletion Script - Simple Version")
    print("=" * 50)
    print(f"Database DSN: {DB_DSN}")
    print(f"Base Path: {BASE_PATH}")
    print("=" * 50)
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database. Exiting.")
        print("Make sure the 'Docketwatch' DSN is configured in ODBC Data Sources.")
        sys.exit(1)
    
    cursor = conn.cursor()
    
    total_processed = 0
    total_files_deleted = 0
    total_db_deleted = 0
    batch_num = 1
    
    try:
        while True:
            print(f"\nBatch {batch_num} - Getting next 10 records...")
            
            # Get next batch of documents
            query = """
            SELECT TOP (10) 
                d.doc_id,
                d.doc_uid,
                d.fk_case,
                d.rel_path,
                d.pdf_title,
                d.file_size,
                c.case_name,
                c.case_number,
                c.status
            FROM [docketwatch].[dbo].[documents] d
            INNER JOIN docketwatch.dbo.cases c ON c.id = d.fk_case
            WHERE c.[status] = 'Removed' AND c.case_number = 'Unfiled'
            ORDER BY d.date_downloaded DESC
            """
            
            cursor.execute(query)
            documents = cursor.fetchall()
            
            if not documents:
                print("No more documents to process.")
                break
            
            print(f"Found {len(documents)} documents in this batch")
            
            for doc in documents:
                doc_id, doc_uid, fk_case, rel_path, pdf_title, file_size, case_name, case_number, status = doc
                
                # Construct full file path
                full_path = os.path.join(BASE_PATH, rel_path.replace('/', '\\'))
                
                print(f"\n[{total_processed + 1}] Processing Document ID: {doc_id}")
                print(f"    Title: {pdf_title}")
                print(f"    Case: {case_name} (ID: {fk_case})")
                print(f"    Rel Path: {rel_path}")
                print(f"    Full Path: {full_path}")
                print(f"    Size: {file_size if file_size else 'Unknown'} bytes")
                
                # Check if file exists
                file_exists = os.path.exists(full_path)
                print(f"    File exists: {file_exists}")
                
                file_deleted = False
                db_deleted = False
                
                # Delete file if it exists
                if file_exists:
                    try:
                        os.remove(full_path)
                        file_deleted = True
                        total_files_deleted += 1
                        print(f"    ✓ FILE DELETED: {full_path}")
                    except PermissionError:
                        print(f"    ✗ FILE PERMISSION DENIED: {full_path}")
                    except Exception as e:
                        print(f"    ✗ FILE DELETE ERROR: {e}")
                else:
                    print(f"    - FILE NOT FOUND (will clean database record)")
                
                # Delete database record
                try:
                    delete_query = "DELETE FROM [docketwatch].[dbo].[documents] WHERE doc_id = ?"
                    cursor.execute(delete_query, doc_id)
                    conn.commit()
                    db_deleted = True
                    total_db_deleted += 1
                    print(f"    ✓ DATABASE RECORD DELETED")
                except Exception as e:
                    conn.rollback()
                    print(f"    ✗ DATABASE DELETE ERROR: {e}")
                
                # Summary for this file
                if file_deleted and db_deleted:
                    print(f"    ✓ COMPLETE: File and database record deleted")
                elif not file_exists and db_deleted:
                    print(f"    ✓ CLEANED: Database record deleted (file was missing)")
                elif file_deleted and not db_deleted:
                    print(f"    ⚠ PARTIAL: File deleted but database record remains")
                else:
                    print(f"    ✗ FAILED: Could not complete deletion")
                
                total_processed += 1
            
            batch_num += 1
            print(f"\nBatch {batch_num-1} Summary:")
            print(f"  Documents processed: {len(documents)}")
            print(f"  Running totals - Processed: {total_processed}, Files deleted: {total_files_deleted}, DB records deleted: {total_db_deleted}")
    
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
    
    print("\n" + "=" * 60)
    print("FINAL DELETION SUMMARY")
    print("=" * 60)
    print(f"Total documents processed: {total_processed}")
    print(f"Total files deleted: {total_files_deleted}")
    print(f"Total database records deleted: {total_db_deleted}")
    if total_processed > 0:
        print(f"File deletion rate: {(total_files_deleted/total_processed)*100:.1f}%")
        print(f"Database deletion rate: {(total_db_deleted/total_processed)*100:.1f}%")
    print("=" * 60)
    print("Script completed.")

if __name__ == "__main__":
    main()
