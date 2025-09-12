#!/usr/bin/env python3
"""
Simple PDF Missing Status Updater

This script finds documents marked as downloaded but with missing PDF files
and updates their status to 'Missing'.

USAGE:
python update_missing_pdf_status.py
"""

import os
import pyodbc
import time

# PDF storage location
FINAL_PDF_DIR = r"\\10.146.176.84\general\docketwatch\docs"

def log_message(message):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

def check_and_update_missing_pdfs():
    """Check for missing PDFs and update their status"""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        log_message("🔍 CHECKING FOR MISSING PDF FILES")
        log_message("=" * 50)
        
        # Query for documents that should have files
        query = """
            SELECT 
                doc_uid,
                doc_id,
                pdf_no,
                rel_path,
                fk_case,
                status
            FROM docketwatch.dbo.documents
            WHERE rel_path IS NOT NULL 
            AND date_downloaded IS NOT NULL
            AND (status IS NULL OR status != 'Missing')
            ORDER BY fk_case, doc_id
        """
        
        cursor.execute(query)
        documents = cursor.fetchall()
        
        if not documents:
            log_message("📭 No documents found to check")
            return
        
        log_message(f"📄 Checking {len(documents)} documents...")
        
        missing_count = 0
        updated_count = 0
        
        for doc in documents:
            doc_uid, doc_id, pdf_no, rel_path, fk_case, current_status = doc
            
            # Construct full file path - rel_path already includes cases\{case_id}\filename
            full_path = os.path.join(FINAL_PDF_DIR, rel_path)
            full_path = os.path.normpath(full_path)
            
            # Check if file exists
            if not os.path.exists(full_path) or not os.path.isfile(full_path) or os.path.getsize(full_path) == 0:
                missing_count += 1
                
                # Update status to Missing
                try:
                    cursor.execute("""
                        UPDATE docketwatch.dbo.documents 
                        SET status = 'Missing'
                        WHERE doc_uid = ?
                    """, (doc_uid,))
                    
                    updated_count += 1
                    log_message(f"📝 Document {doc_id} (PDF #{pdf_no}) - Status updated to 'Missing'")
                    
                except Exception as e:
                    log_message(f"❌ Error updating document {doc_id}: {e}")
        
        # Commit changes
        conn.commit()
        
        log_message("=" * 50)
        log_message(f"📊 RESULTS:")
        log_message(f"   📄 Documents checked: {len(documents)}")
        log_message(f"   ❌ Missing files found: {missing_count}")
        log_message(f"   📝 Statuses updated: {updated_count}")
        log_message("=" * 50)
        
        if missing_count > 0:
            log_message(f"💡 {missing_count} documents have missing PDF files and have been marked as 'Missing'")
        else:
            log_message("✅ All documents have their PDF files present")
    
    except Exception as e:
        log_message(f"❌ Error: {e}")
        return False
    
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass
    
    return True

if __name__ == "__main__":
    success = check_and_update_missing_pdfs()
    
    if not success:
        exit(1)
