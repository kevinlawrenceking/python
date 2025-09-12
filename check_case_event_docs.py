#!/usr/bin/env python3
"""
Simple Case Event Document Status Checker
Shows what documents are available for download for a given case event ID.
"""

import sys
import pyodbc
import time

def log_message(message):
    """Simple logging function"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

def check_case_event_documents(case_event_id):
    """Check documents available for a case event"""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print(f"📋 CASE EVENT DOCUMENT STATUS")
        print("=" * 50)
        print(f"Case Event ID: {case_event_id}")
        print("=" * 50)
        
        # Get case event details
        cursor.execute("""
            SELECT ce.event_no, ce.event_description, c.case_name, c.case_id
            FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.cases c ON ce.fk_case = c.case_id
            WHERE ce.case_event_id = ?
        """, (case_event_id,))
        
        event_row = cursor.fetchone()
        if not event_row:
            print(f"❌ Case event not found: {case_event_id}")
            return False
        
        event_no, event_description, case_name, case_id = event_row
        
        print(f"📁 Case: {case_name}")
        print(f"📄 Event {event_no}: {event_description}")
        print(f"🔗 Case ID: {case_id}")
        print()
        
        # Get documents for this event
        cursor.execute("""
            SELECT 
                doc_id,
                pdf_url,
                pdf_no,
                rel_path,
                date_downloaded,
                status,
                error_message
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
            ORDER BY doc_id
        """, (case_event_id,))
        
        documents = cursor.fetchall()
        
        if not documents:
            print("📭 No documents found for this case event")
            return True
        
        print(f"📄 DOCUMENTS ({len(documents)} found):")
        print("-" * 30)
        
        downloaded_count = 0
        pending_count = 0
        failed_count = 0
        
        for doc in documents:
            doc_id, pdf_url, pdf_no, rel_path, date_downloaded, status, error_message = doc
            
            print(f"\n📄 Document {doc_id} (PDF #{pdf_no})")
            print(f"   URL: {pdf_url[:80]}..." if pdf_url and len(pdf_url) > 80 else f"   URL: {pdf_url}")
            
            if date_downloaded:
                print(f"   ✅ Downloaded: {date_downloaded}")
                print(f"   📁 Path: {rel_path}")
                downloaded_count += 1
            elif status == 'failed':
                print(f"   ❌ Failed: {error_message}")
                failed_count += 1
            else:
                print(f"   ⏳ Status: Pending download")
                pending_count += 1
        
        print("\n" + "=" * 50)
        print("📊 SUMMARY:")
        print(f"   ✅ Downloaded: {downloaded_count}")
        print(f"   ⏳ Pending: {pending_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📄 Total: {len(documents)}")
        
        if pending_count > 0:
            print(f"\n💡 To download pending documents, run:")
            print(f"   python lightweight_enhanced_downloader.py {case_event_id}")
        
        return True
        
    except Exception as e:
        log_message(f"❌ Error checking documents: {e}")
        return False
    
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_case_event_docs.py <case_event_id>")
        print("\nExample:")
        print("python check_case_event_docs.py CC8013B7-EF21-428A-95A7-5053492BF184")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    success = check_case_event_documents(case_event_id)
    
    if not success:
        sys.exit(1)
