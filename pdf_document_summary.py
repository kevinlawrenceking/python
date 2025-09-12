#!/usr/bin/env python3
"""
PDF Document Management Summary
Shows the current status of all PDF documents and what actions can be taken.
"""

import pyodbc
import time

def log_message(message):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

def show_document_summary():
    """Show summary of all document statuses"""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print("📊 PDF DOCUMENT MANAGEMENT SUMMARY")
        print("=" * 60)
        
        # Get total document counts by status
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM docketwatch.dbo.documents
            GROUP BY status
            ORDER BY COUNT(*) DESC
        """)
        
        status_counts = cursor.fetchall()
        
        print("📄 DOCUMENT STATUS BREAKDOWN:")
        print("-" * 40)
        
        total_docs = 0
        for row in status_counts:
            status = row[0] if row[0] else 'NULL/Pending'
            count = row[1]
            total_docs += count
            print(f"   {status:15} : {count:,}")
        
        print(f"   {'TOTAL':15} : {total_docs:,}")
        
        # Get documents with download info
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN rel_path IS NOT NULL AND date_downloaded IS NOT NULL THEN 'Downloaded'
                    WHEN rel_path IS NOT NULL THEN 'Has Path'
                    ELSE 'No Path'
                END as download_status,
                COUNT(*) as count
            FROM docketwatch.dbo.documents
            GROUP BY 
                CASE 
                    WHEN rel_path IS NOT NULL AND date_downloaded IS NOT NULL THEN 'Downloaded'
                    WHEN rel_path IS NOT NULL THEN 'Has Path'
                    ELSE 'No Path'
                END
            ORDER BY COUNT(*) DESC
        """)
        
        download_counts = cursor.fetchall()
        
        print("\n📥 DOWNLOAD STATUS BREAKDOWN:")
        print("-" * 40)
        
        for row in download_counts:
            status = row[0]
            count = row[1]
            print(f"   {status:15} : {count:,}")
        
        # Get recent missing documents
        cursor.execute("""
            SELECT TOP 10
                doc_id,
                fk_case,
                error_message,
                rel_path
            FROM docketwatch.dbo.documents
            WHERE status = 'Missing'
            ORDER BY doc_uid DESC
        """)
        
        missing_docs = cursor.fetchall()
        
        if missing_docs:
            print(f"\n❌ RECENT MISSING DOCUMENTS (Top 10):")
            print("-" * 40)
            
            for doc in missing_docs:
                doc_id, case_id, error_msg, rel_path = doc
                print(f"   Doc {doc_id} (Case {case_id})")
                print(f"      Path: {rel_path}")
                print(f"      Error: {error_msg}")
                print()
        
        # Show available tools
        print("🛠️  AVAILABLE TOOLS:")
        print("-" * 40)
        print("   1. update_missing_pdf_status.py  - Check for missing PDF files")
        print("   2. check_pdf_existence.py        - Detailed PDF existence checker")
        print("   3. check_case_event_docs.py      - Check specific case event documents")
        print("   4. simple_pacer_pdf_test.html    - Test PDF downloads for case events")
        print("   5. lightweight_enhanced_downloader.py - Download PDFs for case events")
        
        print("\n💡 NEXT ACTIONS:")
        print("-" * 40)
        
        cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE status = 'Missing'")
        missing_count = cursor.fetchone()[0]
        
        if missing_count > 0:
            print(f"   • {missing_count} documents marked as 'Missing' could be re-downloaded")
            print(f"   • Run the lightweight enhanced downloader on their case events")
            print(f"   • Use --reset-missing option to reset them for re-download")
        
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.documents 
            WHERE rel_path IS NULL AND date_downloaded IS NULL
        """)
        never_downloaded = cursor.fetchone()[0]
        
        if never_downloaded > 0:
            print(f"   • {never_downloaded} documents have never been downloaded")
            print(f"   • These need their case events to be processed through the pipeline")
        
        print("\n" + "=" * 60)
        
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
    show_document_summary()
