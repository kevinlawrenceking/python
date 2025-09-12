#!/usr/bin/env python3
"""
Check documents table for existing PACER unique identifiers.
Show example of unique numbers and case event relationships.
"""

import pyodbc
import sys
import os

def check_documents_table_for_pacer_ids():
    """Check what PACER identifiers are already stored in documents table"""
    
    try:
        # Connect to database
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.100;"
            "DATABASE=docketwatch;"
            "Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
        
        print("🔍 CHECKING DOCUMENTS TABLE FOR PACER IDENTIFIERS")
        print("=" * 60)
        
        # First, check the documents table structure
        print("\n📋 DOCUMENTS TABLE STRUCTURE:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'documents' 
              AND TABLE_SCHEMA = 'dbo'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        for col in columns:
            col_name, data_type, nullable, max_length = col
            length_info = f"({max_length})" if max_length else ""
            nullable_info = "NULL" if nullable == "YES" else "NOT NULL"
            print(f"   {col_name}: {data_type}{length_info} {nullable_info}")
        
        # Check for recent documents with case event relationships
        print(f"\n🔗 RECENT DOCUMENTS WITH CASE EVENT RELATIONSHIPS:")
        print("-" * 50)
        cursor.execute("""
            SELECT TOP 10
                d.id as doc_id,
                d.fk_case_events as case_event_id,
                d.document_number,
                d.document_url,
                d.pdf_title,
                ce.event_no,
                ce.event_description,
                c.case_name
            FROM docketwatch.dbo.documents d
            LEFT JOIN docketwatch.dbo.case_events ce ON d.fk_case_events = ce.id
            LEFT JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE d.created_at >= DATEADD(day, -7, GETDATE())
              AND d.fk_case_events IS NOT NULL
            ORDER BY d.created_at DESC
        """)
        
        recent_docs = cursor.fetchall()
        if recent_docs:
            print(f"Found {len(recent_docs)} recent documents:")
            for i, doc in enumerate(recent_docs, 1):
                doc_id, case_event_id, doc_number, doc_url, pdf_title, event_no, event_desc, case_name = doc
                
                # Extract potential PACER IDs from URL
                pacer_url_id = None
                if doc_url and '/doc1/' in doc_url:
                    try:
                        pacer_url_id = doc_url.split('/doc1/')[1].split('?')[0]
                    except:
                        pass
                
                print(f"\n   {i}. Document ID: {doc_id}")
                print(f"      Case Event ID: {case_event_id}")
                print(f"      Document Number: {doc_number}")
                print(f"      PACER URL ID: {pacer_url_id}")
                print(f"      Event No: {event_no}")
                print(f"      Case: {case_name[:40] if case_name else 'N/A'}...")
                print(f"      Description: {event_desc[:60] if event_desc else 'N/A'}...")
                
                if i <= 3:  # Show detailed info for first 3
                    print(f"      Full URL: {doc_url}")
        else:
            print("No recent documents found with case event relationships")
        
        # Check for specific patterns in document_url field
        print(f"\n🔍 PACER URL PATTERNS IN DOCUMENTS:")
        print("-" * 40)
        cursor.execute("""
            SELECT TOP 5
                document_url,
                document_number,
                fk_case_events
            FROM docketwatch.dbo.documents
            WHERE document_url LIKE '%/doc1/%'
              AND created_at >= DATEADD(day, -30, GETDATE())
            ORDER BY created_at DESC
        """)
        
        url_patterns = cursor.fetchall()
        for url, doc_num, case_event_id in url_patterns:
            # Extract PACER URL ID
            pacer_url_id = None
            if url and '/doc1/' in url:
                try:
                    pacer_url_id = url.split('/doc1/')[1].split('?')[0].split('/')[0]
                except:
                    pass
            
            print(f"   Document Number: {doc_num}")
            print(f"   Case Event ID: {case_event_id}")
            print(f"   PACER URL ID: {pacer_url_id}")
            print(f"   Full URL: {url}")
            print()
        
        # Look for any existing PACER-like fields
        print(f"\n🔍 CHECKING FOR EXISTING PACER IDENTIFIER FIELDS:")
        print("-" * 50)
        pacer_like_fields = []
        for col in columns:
            col_name = col[0].lower()
            if any(keyword in col_name for keyword in ['pacer', 'doc', 'number', 'url', 'id']):
                pacer_like_fields.append(col[0])
        
        if pacer_like_fields:
            print("Found potential PACER-related fields:")
            for field in pacer_like_fields:
                print(f"   - {field}")
                
                # Show sample data for this field
                cursor.execute(f"""
                    SELECT TOP 3 [{field}], fk_case_events 
                    FROM docketwatch.dbo.documents 
                    WHERE [{field}] IS NOT NULL 
                      AND created_at >= DATEADD(day, -7, GETDATE())
                """)
                samples = cursor.fetchall()
                for sample in samples:
                    print(f"     Example: {sample[0]} (Case Event: {sample[1]})")
        
        conn.close()
        
        print(f"\n🎯 EXAMPLES FOR VERIFICATION:")
        print("=" * 40)
        print("Based on the data above, here are concrete examples to check:")
        print()
        if recent_docs:
            example_doc = recent_docs[0]
            doc_id, case_event_id, doc_number, doc_url, pdf_title, event_no, event_desc, case_name = example_doc
            
            pacer_url_id = None
            if doc_url and '/doc1/' in doc_url:
                try:
                    pacer_url_id = doc_url.split('/doc1/')[1].split('?')[0]
                except:
                    pass
            
            print(f"✅ EXAMPLE TO CHECK:")
            print(f"   Case Event ID: {case_event_id}")
            print(f"   Document Number: {doc_number} (check if this matches PACER doc #)")
            print(f"   PACER URL ID: {pacer_url_id} (extracted from document_url)")
            print(f"   Event Number: {event_no}")
            print()
            print("❓ Questions to verify:")
            print(f"   1. Does document_number '{doc_number}' match the PACER document number?")
            print(f"   2. Is '{pacer_url_id}' the unique PACER document ID?")
            print(f"   3. Can we use these for bulletproof duplicate detection?")
        
    except Exception as e:
        print(f"❌ Error checking documents table: {e}")
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    check_documents_table_for_pacer_ids()
