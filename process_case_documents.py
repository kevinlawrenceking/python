"""
Case Document Processor - Loop Version

Processes all documents for a specific case using the improved AI summarizer.
Documents are processed in newest-first order (by date_downloaded).
"""

import os
import sys
import pyodbc
from datetime import datetime
from summarize_document_event import process_single_pdf


def get_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn, conn.cursor()


def get_case_documents(cursor, case_id):
    """
    Get all documents for a specific case that need AI processing.
    Returns documents in newest-first order.
    """
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.pdf_title,
            d.date_downloaded,
            d.rel_path,
            c.case_name,
            c.case_number,
            e.event_description,
            e.event_date
        FROM docketwatch.dbo.documents d
        LEFT JOIN docketwatch.dbo.case_events e ON e.id = d.fk_case_event
        JOIN docketwatch.dbo.cases c ON c.id = d.fk_case
        WHERE d.fk_case = ?
          AND d.summary_ai IS NULL
          AND d.rel_path IS NOT NULL
          AND d.rel_path != 'pending'
        ORDER BY d.date_downloaded DESC
    """, (case_id,))
    
    return cursor.fetchall()


def process_case_documents(case_id):
    """
    Process all documents for a specific case with the improved AI summarizer.
    """
    conn, cursor = get_cursor()
    
    try:
        # Get case info first
        cursor.execute("""
            SELECT case_number, case_name 
            FROM docketwatch.dbo.cases 
            WHERE id = ?
        """, (case_id,))
        
        case_info = cursor.fetchone()
        if not case_info:
            print(f"Case ID {case_id} not found.")
            return
        
        case_number, case_name = case_info
        print(f"Processing case: {case_number} - {case_name}")
        print("=" * 60)
        
        # Get documents to process
        documents = get_case_documents(cursor, case_id)
        
        if not documents:
            print("No documents found that need AI processing.")
            return
        
        print(f"Found {len(documents)} documents to process")
        print()
        
        # Process each document
        for i, doc_row in enumerate(documents, 1):
            doc_uid, pdf_title, date_downloaded, rel_path, case_name, case_number, event_desc, event_date = doc_row
            
            print(f"[{i}/{len(documents)}] Processing: {pdf_title or 'Untitled'}")
            print(f"  Doc UID: {doc_uid}")
            print(f"  Downloaded: {date_downloaded}")
            print(f"  Event: {event_desc or 'No event description'}")
            print(f"  Path: {rel_path}")
            
            try:
                # Process this document
                process_single_pdf(str(doc_uid))
                print(f"  ✅ SUCCESS: Document processed")
                
            except Exception as e:
                print(f"  ❌ ERROR: {e}")
            
            print("-" * 40)
        
        print(f"\n🎉 Completed processing {len(documents)} documents for case {case_number}")
        
    finally:
        cursor.close()
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python process_case_documents.py <case_id>")
        print("Example: python process_case_documents.py 131835")
        return
    
    try:
        case_id = int(sys.argv[1])
        process_case_documents(case_id)
    except ValueError:
        print("Error: Case ID must be a number")
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()