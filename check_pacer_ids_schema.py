#!/usr/bin/env python3
"""
Check actual PACER identifiers in documents table based on schema.
Focus on doc_id, pdf_no, and pdf_url fields.
"""

import pyodbc

def check_pacer_identifiers_in_documents():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.100;"
            "DATABASE=docketwatch;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        
        print("🔍 CHECKING PACER IDENTIFIERS IN DOCUMENTS TABLE")
        print("=" * 55)
        
        # Check recent documents with PACER identifiers
        cursor.execute("""
            SELECT TOP 5
                d.doc_id,
                d.pdf_no,
                d.pdf_url,
                d.fk_case_event,
                ce.event_no,
                ce.event_description
            FROM docketwatch.dbo.documents d
            JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            WHERE d.pdf_url IS NOT NULL
              AND d.date_downloaded >= DATEADD(day, -7, GETDATE())
            ORDER BY d.date_downloaded DESC
        """)
        
        results = cursor.fetchall()
        
        if results:
            print(f"📋 Found {len(results)} recent documents:")
            print()
            
            for i, row in enumerate(results, 1):
                doc_id, pdf_no, pdf_url, fk_case_event, event_no, event_desc = row
                
                # Extract PACER URL ID from pdf_url
                pacer_url_id = None
                if pdf_url and '/doc1/' in pdf_url:
                    try:
                        pacer_url_id = pdf_url.split('/doc1/')[1].split('?')[0].split('/')[0]
                    except:
                        pass
                
                print(f"📄 Document {i}:")
                print(f"   doc_id: {doc_id}")
                print(f"   pdf_no: {pdf_no}")
                print(f"   fk_case_event: {fk_case_event}")
                print(f"   event_no: {event_no}")
                print(f"   PACER URL ID: {pacer_url_id}")
                print(f"   Event Description: {event_desc[:50] if event_desc else 'N/A'}...")
                print(f"   Full URL: {pdf_url}")
                print()
        else:
            print("❌ No recent documents found")
        
        # Check patterns in doc_id field
        print("🔍 ANALYZING doc_id PATTERNS:")
        cursor.execute("""
            SELECT TOP 10 doc_id, pdf_no, pdf_url
            FROM docketwatch.dbo.documents
            WHERE doc_id IS NOT NULL
              AND date_downloaded >= DATEADD(day, -30, GETDATE())
            ORDER BY date_downloaded DESC
        """)
        
        doc_patterns = cursor.fetchall()
        for doc_id, pdf_no, pdf_url in doc_patterns:
            pacer_url_id = None
            if pdf_url and '/doc1/' in pdf_url:
                try:
                    pacer_url_id = pdf_url.split('/doc1/')[1].split('?')[0].split('/')[0]
                except:
                    pass
            
            print(f"   doc_id: {doc_id}")
            print(f"   pdf_no: {pdf_no}")
            print(f"   URL ID: {pacer_url_id}")
            print()
        
        conn.close()
        
        print("🎯 DUPLICATE DETECTION STRATEGY:")
        print("=" * 40)
        print("Based on your schema, we can use:")
        print("1. doc_id (unique constraint - perfect!)")
        print("2. pdf_no (likely PACER document number)")
        print("3. Extract PACER ID from pdf_url")
        print()
        print("✅ BULLETPROOF METHOD:")
        print("   Check if doc_id or pdf_no already exists")
        print("   for this case before creating case_event")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_pacer_identifiers_in_documents()
