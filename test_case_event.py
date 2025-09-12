#!/usr/bin/env python3
"""
Simple script to check case event and run insert_documents_for_event
"""

import pyodbc

def main():
    case_event_id = "EAF1BF1B-88F7-4231-9413-51D9C7EDCC5D"
    
    print(f"Connecting to database...")
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("✅ Database connected")
        
        # Check if case event exists
        print(f"Checking case event: {case_event_id}")
        cursor.execute("""
            SELECT e.id, e.event_description, c.case_name, c.case_number, c.id as case_id
            FROM docketwatch.dbo.case_events e
            INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
            WHERE e.id = ?
        """, (case_event_id,))
        
        row = cursor.fetchone()
        if not row:
            print(f"❌ Case event not found: {case_event_id}")
            return
            
        event_id, event_desc, case_name, case_number, case_id = row
        print(f"✅ Found event: {case_number} - {case_name}")
        print(f"   Event: {event_desc}")
        print(f"   Case ID: {case_id}")
        
        # Check current documents
        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.documents 
            WHERE fk_case_event = ?
        """, (case_event_id,))
        doc_count = cursor.fetchone()[0]
        print(f"Current documents: {doc_count}")
        
        # Check if case directory exists
        case_dir = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}"
        print(f"Checking directory: {case_dir}")
        
        import os
        if os.path.exists(case_dir):
            pdf_files = [f for f in os.listdir(case_dir) if f.endswith('.pdf')]
            print(f"✅ Directory exists with {len(pdf_files)} PDF files")
            for pdf in pdf_files[:5]:  # Show first 5
                print(f"   - {pdf}")
        else:
            print(f"❌ Directory does not exist")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
