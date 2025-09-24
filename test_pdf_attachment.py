#!/usr/bin/env python3
import os
import pyodbc

def test_pdf_path_construction():
    """Test PDF path construction for attachment debugging."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # Get documents for case 107756
        cursor.execute("""
            SELECT TOP 3 
                d.doc_id, 
                d.fk_case, 
                d.rel_path, 
                d.pdf_title,
                d.date_downloaded
            FROM docketwatch.dbo.documents d
            WHERE d.fk_case = ?
                AND d.rel_path IS NOT NULL 
                AND d.rel_path != 'pending'
            ORDER BY d.doc_uid DESC
        """, (107756,))

        docs = cursor.fetchall()
        
        if not docs:
            print("❌ No documents found for case 107756")
            return
        
        print(f"📄 Found {len(docs)} documents for case 107756:")
        print("=" * 80)
        
        base_docs_dir = r"\\10.146.176.84\general\docketwatch\docs"
        
        for doc in docs:
            doc_id, fk_case, rel_path, pdf_title, date_downloaded = doc
            
            print(f"📋 Document ID: {doc_id}")
            print(f"   Case ID: {fk_case}")
            print(f"   rel_path: {rel_path}")
            print(f"   pdf_title: {pdf_title}")
            print(f"   downloaded: {date_downloaded}")
            
            # Construct full path as script does
            full_path = os.path.join(base_docs_dir, rel_path)
            print(f"   Full path: {full_path}")
            
            # Check if file exists
            if os.path.exists(full_path):
                file_size = os.path.getsize(full_path)
                print(f"   ✅ File exists! Size: {file_size:,} bytes")
            else:
                print(f"   ❌ File does NOT exist")
                
                # Try alternative path constructions
                if rel_path.startswith("cases\\"):
                    alt_path1 = os.path.join(base_docs_dir, rel_path.replace("cases\\", ""))
                    if os.path.exists(alt_path1):
                        print(f"   🔧 Alternative path works: {alt_path1}")
            
            print()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_pdf_path_construction()