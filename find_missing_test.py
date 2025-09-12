#!/usr/bin/env python3
"""
Find Some Missing PDFs for Testing
"""

import os
import pyodbc
import time

def find_missing_pdfs():
    """Find some documents with missing PDFs for testing"""
    
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # Query for documents that should have files
        query = """
            SELECT TOP 50
                doc_uid,
                doc_id,
                pdf_no,
                rel_path,
                fk_case,
                status,
                date_downloaded
            FROM docketwatch.dbo.documents
            WHERE rel_path IS NOT NULL 
            AND date_downloaded IS NOT NULL
            ORDER BY doc_uid ASC
        """
        
        cursor.execute(query)
        documents = cursor.fetchall()
        
        FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs"
        
        print(f"Checking {len(documents)} documents for missing files...")
        
        missing_count = 0
        exists_count = 0
        
        for doc in documents:
            doc_uid, doc_id, pdf_no, rel_path, fk_case, current_status, date_downloaded = doc
            
            # Construct full file path
            full_path = os.path.join(FINAL_PDF_DIR, rel_path)
            full_path = os.path.normpath(full_path)
            
            # Check if file exists
            exists = os.path.exists(full_path) and os.path.isfile(full_path) and os.path.getsize(full_path) > 0
            
            if exists:
                exists_count += 1
            else:
                missing_count += 1
                print(f"❌ MISSING: Document {doc_id} (PDF #{pdf_no})")
                print(f"   Case: {fk_case}")
                print(f"   Downloaded: {date_downloaded}")
                print(f"   Status: {current_status}")
                print(f"   Path: {full_path}")
                print()
                
                if missing_count >= 5:  # Show only first 5 missing files
                    break
        
        print(f"Summary: {exists_count} exist, {missing_count} missing (showing first 5)")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_missing_pdfs()
