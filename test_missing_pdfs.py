#!/usr/bin/env python3
"""
Test Missing PDF Status Updater
A simpler version to test the functionality step by step.
"""

import os
import pyodbc
import time

def test_missing_pdfs():
    """Test function to check for missing PDFs"""
    
    try:
        print("Connecting to database...")
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        print("✅ Database connected")
        
        # Test query - just get a small sample
        query = """
            SELECT TOP 5
                doc_uid,
                doc_id,
                pdf_no,
                rel_path,
                fk_case,
                status
            FROM docketwatch.dbo.documents
            WHERE rel_path IS NOT NULL 
            AND date_downloaded IS NOT NULL
            ORDER BY doc_uid DESC
        """
        
        print("Executing query...")
        cursor.execute(query)
        documents = cursor.fetchall()
        print(f"✅ Found {len(documents)} test documents")
        
        if not documents:
            print("No documents found to test")
            return
        
        FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs"  # Remove the 'cases' part
        print(f"PDF Directory: {FINAL_PDF_DIR}")
        
        for doc in documents:
            doc_uid, doc_id, pdf_no, rel_path, fk_case, current_status = doc
            
            print(f"\n📄 Document {doc_id} (PDF #{pdf_no})")
            print(f"   Case: {fk_case}")
            print(f"   Rel Path: {rel_path}")
            print(f"   Status: {current_status}")
            
            # Construct full file path - rel_path already includes cases\{case_id}\filename
            full_path = os.path.join(FINAL_PDF_DIR, rel_path)
            full_path = os.path.normpath(full_path)
            print(f"   Full Path: {full_path}")
            
            # Check if file exists
            exists = os.path.exists(full_path)
            print(f"   File Exists: {exists}")
            
            if exists:
                is_file = os.path.isfile(full_path)
                file_size = os.path.getsize(full_path) if is_file else 0
                print(f"   Is File: {is_file}, Size: {file_size} bytes")
        
        cursor.close()
        conn.close()
        print("✅ Test completed successfully")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_missing_pdfs()
