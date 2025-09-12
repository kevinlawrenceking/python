#!/usr/bin/env python3
"""
Script to run insert_documents_for_event function for a specific case event.
"""

import pyodbc
import os
import random

def insert_documents_for_event_local(cursor, case_event_id, tool_id=2):
    """Local version of the insert_documents_for_event function"""
    # Check if documents already exist for this event
    cursor.execute("""
        SELECT COUNT(*) 
        FROM docketwatch.dbo.documents 
        WHERE fk_case_event = ?
    """, (case_event_id,))
    existing_count = cursor.fetchone()[0]
    if existing_count > 0:
        print(f"Documents already exist for this event: {existing_count}")
        return 0  # already has documents

    # Get the case ID to find the directory
    cursor.execute("""
        SELECT fk_cases 
        FROM docketwatch.dbo.case_events 
        WHERE id = ?
    """, (case_event_id,))
    case_row = cursor.fetchone()
    if not case_row:
        print("Case event not found")
        return 0
    
    case_id = case_row[0]
    
    # Look for PDF files in the case directory
    case_dir = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}"
    
    if not os.path.exists(case_dir):
        print(f"Case directory does not exist: {case_dir}")
        return 0
    
    pdf_files = [f for f in os.listdir(case_dir) if f.endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found in case directory")
        return 0
    
    print(f"Found {len(pdf_files)} PDF files to process")
    documents_created = 0
    
    for pdf_file in pdf_files:
        # Generate a unique doc_id
        cursor.execute("SELECT GETDATE()")
        timestamp = cursor.fetchone()[0]
        unique_doc_id = str(int(timestamp.timestamp() * 1000) + random.randint(1, 999))
        
        # Create relative path
        rel_path = f"cases\\{case_id}\\{pdf_file}"
        
        print(f"Creating document record for: {pdf_file}")
        
        # INSERT into documents table
        cursor.execute("""
            INSERT INTO docketwatch.dbo.documents (
                fk_case_event, fk_case, fk_tool, pdf_title, rel_path, 
                pdf_type, pdf_no, doc_id, date_downloaded
            ) VALUES (?, ?, ?, ?, ?, 'Filing', 0, ?, GETDATE())
        """, (case_event_id, case_id, tool_id, pdf_file, rel_path, unique_doc_id))
        
        documents_created += 1
    
    cursor.connection.commit()
    print(f"YES Created {documents_created} document records")
    return documents_created

def main():
    case_event_id = "E0B4AFFE-302E-41E9-8DEF-7322992D8D12"
    
    print(f"Starting script for case event ID: {case_event_id}")
    
    try:
        # Get database connection
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("YEs Database connected")
        
        # Check if the case event exists
        cursor.execute("""
            SELECT e.id, e.event_description, c.case_name, c.case_number
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            WHERE e.id = ?
        """, (case_event_id,))
        
        event_row = cursor.fetchone()
        if not event_row:
            print(f"NO Case event ID {case_event_id} not found in database.")
            return 1
        
        event_id, event_desc, case_name, case_number = event_row
        print(f"YES Found case event:")
        print(f"   Event ID: {event_id}")
        print(f"   Description: {event_desc}")
        print(f"   Case: {case_number} - {case_name}")
        
        # Run the insert_documents_for_event function
        print(f"\nRunning insert_documents_for_event...")
        documents_created = insert_documents_for_event_local(cursor, case_event_id)
        
        print(f"\nYES Function completed!")
        print(f"Documents created: {documents_created}")
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"X Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    print(f"\nScript finished with exit code: {exit_code}")
