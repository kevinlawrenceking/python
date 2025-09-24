#!/usr/bin/env python3
import os
import pyodbc

def test_new_pdf_path_construction():
    """Test the new PDF path construction using the formula you provided."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # Test with the specific event you mentioned
        event_id = 'ECBEE0BE-9665-42CA-8804-AD61B0548671'
        
        print(f"🧪 Testing PDF path construction for event: {event_id}")
        print("=" * 70)
        
        # Get documents for this event using your formula
        cursor.execute("""
            SELECT 
                doc_id,
                fk_case,
                pdf_title,
                rel_path,
                '\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\' 
                + cast(fk_case as varchar(20)) 
                + '\\E' 
                + cast(doc_id as varchar(20))
                + '.pdf' as local_path
            FROM documents
            WHERE fk_case_event = ?
        """, (event_id,))

        docs = cursor.fetchall()
        
        if not docs:
            print("❌ No documents found for this event")
            return
        
        print(f"📄 Found {len(docs)} documents for event:")
        print()
        
        base_docs_dir = r"\\10.146.176.84\general\docketwatch\docs"
        
        for doc in docs:
            doc_id, fk_case, pdf_title, rel_path, local_path = doc
            
            print(f"📋 Document ID: {doc_id}")
            print(f"   Case ID: {fk_case}")
            print(f"   PDF Title: {pdf_title}")
            print(f"   rel_path (database): {rel_path}")
            print(f"   Formula path: {local_path}")
            
            # Test the new construction method
            new_path = f"{base_docs_dir}\\cases\\{fk_case}\\E{doc_id}.pdf"
            print(f"   Script path: {new_path}")
            
            # Check which paths exist
            paths_to_check = [
                ("Formula path", local_path),
                ("Script path", new_path),
            ]
            
            if rel_path:
                old_path = os.path.join(base_docs_dir, rel_path)
                paths_to_check.append(("Old rel_path method", old_path))
            
            print("   File existence check:")
            for path_name, path in paths_to_check:
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    print(f"     ✅ {path_name}: EXISTS ({file_size:,} bytes)")
                else:
                    print(f"     ❌ {path_name}: NOT FOUND")
            
            print()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_new_pdf_path_construction()