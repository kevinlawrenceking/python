#!/usr/bin/env python3
"""
Quick Test - Enhanced PDF Downloader with Debug
"""

import sys
import pyodbc

def quick_test_enhanced(case_event_id):
    """Quick test with debug output"""
    
    print(f"🧪 QUICK TEST: Enhanced PDF Downloader")
    print(f"Case Event ID: {case_event_id}")
    print("=" * 50)
    
    try:
        # Database setup
        print("1. Connecting to database...")
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        print("✅ Connected")
        
        # Check documents
        print("2. Checking documents...")
        cursor.execute("""
            SELECT COUNT(*)
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
        """, (case_event_id,))
        
        doc_count = cursor.fetchone()[0]
        print(f"✅ Found {doc_count} documents")
        
        if doc_count == 0:
            print("❌ No documents to process")
            return
        
        # Import and run enhanced downloader
        print("3. Importing enhanced downloader...")
        try:
            import enhanced_pacer_pdf_downloader as epd
            print("✅ Imported successfully")
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return
        
        print("4. Running enhanced downloader...")
        try:
            result = epd.enhanced_pdf_download(case_event_id)
            print(f"✅ Enhanced downloader completed: {result}")
        except Exception as e:
            print(f"❌ Enhanced downloader failed: {e}")
            import traceback
            traceback.print_exc()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_test_enhanced.py <case_event_id>")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    quick_test_enhanced(case_event_id)
