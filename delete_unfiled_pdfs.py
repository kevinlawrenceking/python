#!/usr/bin/env python3
"""
Delete Unfiled PDFs Script
==========================
This script deletes PDF files for unfiled cases with "Removed" status.
It processes 10 files at a time and prints what was deleted.
"""

import pyodbc
import os
import sys
from pathlib import Path

# Database connection settings
DB_DSN = "Docketwatch"  # DSN name from your example

# Base file path
BASE_PATH = r"\\10.146.176.84\general\DOCKETWATCH\docs"

def get_db_connection():
    """Create database connection using DSN"""
    try:
        conn_str = f"DSN={DB_DSN};TrustServerCertificate=yes;"
        conn = pyodbc.connect(conn_str)
        print(f"Connected to database using DSN: {DB_DSN}")
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        print(f"Make sure the DSN '{DB_DSN}' is configured on this system")
        return None

def get_unfiled_documents(cursor, limit=10):
    """Get unfiled documents to delete"""
    query = """
    SELECT TOP (?) 
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
    
    cursor.execute(query, limit)
    return cursor.fetchall()

def delete_file_safely(file_path):
    """Safely delete a file and return success status"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True, "File deleted successfully"
        else:
            return False, "File not found"
    except PermissionError:
        return False, "Permission denied"
    except Exception as e:
        return False, f"Error: {str(e)}"

def delete_database_record(cursor, doc_id):
    """Delete the database record"""
    try:
        query = "DELETE FROM [docketwatch].[dbo].[documents] WHERE doc_id = ?"
        cursor.execute(query, doc_id)
        return True, "Database record deleted"
    except Exception as e:
        return False, f"Database error: {str(e)}"

def main():
    print("Starting Unfiled PDF Deletion Script")
    print("=" * 50)
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    cursor = conn.cursor()
    
    total_processed = 0
    total_deleted = 0
    batch_num = 1
    
    try:
        while True:
            print(f"\nBatch {batch_num} - Processing next 10 records...")
            
            # Get next batch of documents
            documents = get_unfiled_documents(cursor, 10)
            
            if not documents:
                print("No more documents to process.")
                break
            
            print(f"Found {len(documents)} documents in this batch")
            
            for doc in documents:
                doc_id, doc_uid, fk_case, rel_path, pdf_title, file_size, case_name, case_number, status = doc
                
                # Construct full file path
                full_path = os.path.join(BASE_PATH, rel_path)
                
                print(f"\nProcessing Document ID: {doc_id}")
                print(f"  Title: {pdf_title}")
                print(f"  Case: {case_name} (ID: {fk_case})")
                print(f"  Path: {full_path}")
                print(f"  Size: {file_size if file_size else 'Unknown'} bytes")
                
                # Check if file exists before attempting deletion
                file_exists = os.path.exists(full_path)
                print(f"  File exists: {file_exists}")
                
                if file_exists:
                    # Delete the file
                    file_deleted, file_msg = delete_file_safely(full_path)
                    print(f"  File deletion: {file_msg}")
                    
                    if file_deleted:
                        # Delete database record
                        db_deleted, db_msg = delete_database_record(cursor, doc_id)
                        print(f"  Database deletion: {db_msg}")
                        
                        if db_deleted:
                            conn.commit()
                            total_deleted += 1
                            print(f"  ✓ FULLY DELETED - File and database record removed")
                        else:
                            conn.rollback()
                            print(f"  ✗ PARTIAL - File deleted but database record failed")
                    else:
                        print(f"  ✗ FAILED - Could not delete file")
                else:
                    # File doesn't exist, just delete database record
                    db_deleted, db_msg = delete_database_record(cursor, doc_id)
                    print(f"  Database deletion: {db_msg}")
                    
                    if db_deleted:
                        conn.commit()
                        total_deleted += 1
                        print(f"  ✓ DATABASE CLEANED - Record removed (file was already missing)")
                    else:
                        conn.rollback()
                        print(f"  ✗ FAILED - Could not delete database record")
                
                total_processed += 1
            
            batch_num += 1
            print(f"\nBatch {batch_num-1} completed. Processed: {len(documents)}, Total processed: {total_processed}, Total deleted: {total_deleted}")
    
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        cursor.close()
        conn.close()
    
    print("\n" + "=" * 50)
    print("DELETION SUMMARY")
    print("=" * 50)
    print(f"Total documents processed: {total_processed}")
    print(f"Total successfully deleted: {total_deleted}")
    print(f"Success rate: {(total_deleted/total_processed)*100:.1f}%" if total_processed > 0 else "N/A")
    print("Script completed.")

if __name__ == "__main__":
    main()
