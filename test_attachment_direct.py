#!/usr/bin/env python3
import os
import pyodbc

def test_collect_pdf_attachments_directly():
    """Test the collect_pdf_attachments function directly."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        event_id = 'ECBEE0BE-9665-42CA-8804-AD61B0548671'
        case_id = 107756
        
        print("🧪 Testing collect_pdf_attachments function directly")
        print("=" * 50)
        
        # Simulate the events structure that would be passed to collect_pdf_attachments
        cursor.execute("""
            SELECT d.doc_id, d.fk_case, d.rel_path, d.pdf_title, d.summary_ai_html
            FROM docketwatch.dbo.documents d
            WHERE d.fk_case_event = ?
        """, (event_id,))
        
        doc_row = cursor.fetchone()
        
        if not doc_row:
            print("❌ No document found for event")
            return False
        
        # Create the events structure as it would be in the main script
        events = {
            event_id: {
                "event_description": "Letter",
                "event_date": None,
                "created_at": None,
                "documents": [{
                    "doc_id": doc_row.doc_id,
                    "fk_case": doc_row.fk_case,
                    "pdf_title": doc_row.pdf_title,
                    "summary": doc_row.summary_ai_html if doc_row.summary_ai_html else "",
                    "rel_path": doc_row.rel_path if doc_row.rel_path else ""
                }]
            }
        }
        
        print(f"📋 Document details:")
        print(f"   doc_id: {doc_row.doc_id}")
        print(f"   fk_case: {doc_row.fk_case}")
        print(f"   pdf_title: {doc_row.pdf_title}")
        print(f"   rel_path: {doc_row.rel_path}")
        print()
        
        # Test the collect_pdf_attachments function
        base_docs_dir = r"\\10.146.176.84\general\docketwatch\docs"
        
        # Simulate the function logic
        attachments = []
        
        for event_id, event_data in events.items():
            for doc in event_data["documents"]:
                rel_path = doc.get("rel_path", "")
                doc_id = doc.get("doc_id", "")
                pdf_title = doc.get("pdf_title", "")
                fk_case = doc.get("fk_case", "")
                
                print(f"🔧 Processing document:")
                print(f"   doc_id: {doc_id}")
                print(f"   fk_case: {fk_case}")
                print(f"   rel_path: {rel_path}")
                
                # Skip if no doc_id (document not available)
                if not doc_id or not fk_case:
                    print("❌ Skipping: missing doc_id or fk_case")
                    continue
                
                # Skip if no relative path (document not downloaded yet)
                if not rel_path or rel_path == "pending":
                    print(f"❌ Skipping: not downloaded yet (rel_path: {rel_path})")
                    continue
                
                # Construct full file path using the standard formula
                full_path = f"{base_docs_dir}\\cases\\{fk_case}\\E{doc_id}.pdf"
                print(f"🔗 Constructed path: {full_path}")
                
                # Check if file exists
                if os.path.exists(full_path):
                    file_size = os.path.getsize(full_path)
                    print(f"✅ File exists! Size: {file_size:,} bytes")
                    
                    # Create filename
                    if pdf_title:
                        clean_title = "".join(c for c in pdf_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        filename = f"{clean_title}.pdf" if not clean_title.endswith('.pdf') else clean_title
                    else:
                        filename = f"Document_{doc_id}.pdf"
                    
                    if len(filename) > 100:
                        filename = f"Document_{doc_id}.pdf"
                    
                    attachments.append((full_path, filename))
                    print(f"📎 Added attachment: {filename}")
                else:
                    print(f"❌ File not found: {full_path}")
        
        print(f"\n🎯 Result: {len(attachments)} attachments prepared")
        
        cursor.close()
        conn.close()
        
        return len(attachments) > 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_collect_pdf_attachments_directly()