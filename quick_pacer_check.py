#!/usr/bin/env python3
"""
Quick check for PACER identifiers in documents table.
"""

import pyodbc

def quick_pacer_check():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.100;"
            "DATABASE=docketwatch;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        
        print("🔍 QUICK PACER IDENTIFIER CHECK")
        print("=" * 40)
        
        # Get recent document with case event
        cursor.execute("""
            SELECT TOP 1
                d.document_number,
                d.document_url,
                d.fk_case_events,
                ce.event_no
            FROM docketwatch.dbo.documents d
            JOIN docketwatch.dbo.case_events ce ON d.fk_case_events = ce.id
            WHERE d.document_url IS NOT NULL
              AND d.document_url LIKE '%/doc1/%'
            ORDER BY d.created_at DESC
        """)
        
        result = cursor.fetchone()
        if result:
            doc_number, doc_url, case_event_id, event_no = result
            
            # Extract PACER URL ID
            pacer_url_id = None
            if '/doc1/' in doc_url:
                pacer_url_id = doc_url.split('/doc1/')[1].split('?')[0].split('/')[0]
            
            print(f"📋 EXAMPLE FROM YOUR DATABASE:")
            print(f"   Case Event ID: {case_event_id}")
            print(f"   Document Number: {doc_number}")
            print(f"   Event Number: {event_no}")
            print(f"   PACER URL ID: {pacer_url_id}")
            print(f"   Full URL: {doc_url}")
            
            print(f"\n❓ TO CHECK:")
            print(f"   Does document_number '{doc_number}' = PACER doc number?")
            print(f"   Is '{pacer_url_id}' unique across PACER?")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    quick_pacer_check()
