#!/usr/bin/env python3
"""
Check documents table for PACER identifiers linked to case events.
Corrected relationship: documents.fk_case_event -> case_events.id
"""

import pyodbc

def check_documents_with_case_events():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.100;"
            "DATABASE=docketwatch;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        
        print("🔍 CHECKING DOCUMENTS -> CASE EVENTS RELATIONSHIP")
        print("=" * 50)
        
        # Check recent documents linked to case events
        cursor.execute("""
            SELECT TOP 5
                d.id as doc_id,
                d.fk_case_event,
                d.document_number,
                d.document_url,
                ce.id as case_event_id,
                ce.event_no,
                ce.event_description
            FROM docketwatch.dbo.documents d
            JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            WHERE d.document_url IS NOT NULL
              AND d.created_at >= DATEADD(day, -7, GETDATE())
            ORDER BY d.created_at DESC
        """)
        
        results = cursor.fetchall()
        
        if results:
            print(f"📋 Found {len(results)} recent documents with case events:")
            print()
            
            for i, row in enumerate(results, 1):
                doc_id, fk_case_event, doc_number, doc_url, case_event_id, event_no, event_desc = row
                
                # Extract PACER URL ID if available
                pacer_url_id = None
                if doc_url and '/doc1/' in doc_url:
                    try:
                        pacer_url_id = doc_url.split('/doc1/')[1].split('?')[0].split('/')[0]
                    except:
                        pass
                
                print(f"🔗 Example {i}:")
                print(f"   Document ID: {doc_id}")
                print(f"   fk_case_event: {fk_case_event}")
                print(f"   Case Event ID: {case_event_id}")
                print(f"   Document Number: {doc_number}")
                print(f"   Event No: {event_no}")
                print(f"   PACER URL ID: {pacer_url_id}")
                print(f"   Event Description: {event_desc[:60] if event_desc else 'N/A'}...")
                print(f"   Document URL: {doc_url}")
                print()
        else:
            print("❌ No recent documents found with case event links")
        
        # Check documents table structure
        print("📊 DOCUMENTS TABLE STRUCTURE:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'documents' AND TABLE_SCHEMA = 'dbo'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        for col in columns:
            print(f"   {col[0]}: {col[1]} {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
        
        conn.close()
        
        if results:
            example = results[0]
            doc_number = example[2]
            pacer_url_id = None
            if example[3] and '/doc1/' in example[3]:
                try:
                    pacer_url_id = example[3].split('/doc1/')[1].split('?')[0].split('/')[0]
                except:
                    pass
            
            print("\n🎯 CONCRETE EXAMPLE TO VERIFY:")
            print("=" * 40)
            print(f"Case Event ID: {example[4]}")
            print(f"Document Number: {doc_number}")
            print(f"PACER URL ID: {pacer_url_id}")
            print()
            print("❓ CHECK THESE QUESTIONS:")
            print(f"1. Is document_number '{doc_number}' the same as PACER doc # (like '73' from your HTML)?")
            print(f"2. Is PACER URL ID '{pacer_url_id}' unique (like '127138195871' from your HTML)?")
            print(f"3. Can we use these for duplicate detection in case_events?")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_documents_with_case_events()
