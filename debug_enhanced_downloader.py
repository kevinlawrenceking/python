#!/usr/bin/env python3
"""
Debug Enhanced PDF Downloader
Check what's happening with the enhanced downloader.
"""

import sys
import pyodbc

def debug_enhanced_downloader(case_event_id):
    """Debug the enhanced downloader setup"""
    
    print("🔍 DEBUG ENHANCED PDF DOWNLOADER")
    print(f"Case Event ID: {case_event_id}")
    print("=" * 50)
    
    # Test database connection
    print("\n1️⃣ Testing database connection...")
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Check case event exists
    print("\n2️⃣ Checking case event...")
    try:
        cursor.execute("""
            SELECT fk_cases, event_no
            FROM docketwatch.dbo.case_events
            WHERE id = ?
        """, (case_event_id,))
        
        result = cursor.fetchone()
        if result:
            fk_case, event_no = result
            print(f"✅ Case event found: Case {fk_case}, Event {event_no}")
        else:
            print(f"❌ Case event {case_event_id} not found")
            return
    except Exception as e:
        print(f"❌ Error checking case event: {e}")
        return
    
    # Check for documents
    print("\n3️⃣ Checking for documents...")
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
        """, (case_event_id,))
        
        doc_count = cursor.fetchone()[0]
        print(f"✅ Found {doc_count} documents for this case event")
        
        if doc_count == 0:
            print("⚠️ No documents found - enhanced downloader will have nothing to process")
        
    except Exception as e:
        print(f"❌ Error checking documents: {e}")
        return
    
    # Check PACER credentials
    print("\n4️⃣ Checking PACER credentials...")
    try:
        cursor.execute("SELECT username, pass FROM docketwatch.dbo.tools WHERE id = 2")
        creds = cursor.fetchone()
        if creds and creds[0] and creds[1]:
            print("✅ PACER credentials found in database")
        else:
            print("❌ PACER credentials missing from database")
    except Exception as e:
        print(f"❌ Error checking credentials: {e}")
    
    # Test enhanced downloader import
    print("\n5️⃣ Testing enhanced downloader import...")
    try:
        sys.path.append('.')
        import enhanced_pacer_pdf_downloader as epd
        print("✅ Enhanced downloader imports successfully")
        
        # Check main function exists
        if hasattr(epd, 'enhanced_pdf_download'):
            print("✅ Main function 'enhanced_pdf_download' found")
        else:
            print("❌ Main function 'enhanced_pdf_download' not found")
            
    except Exception as e:
        print(f"❌ Enhanced downloader import failed: {e}")
    
    cursor.close()
    conn.close()
    
    print("\n📋 SUMMARY:")
    print("If all checks passed, you can run:")
    print(f"python enhanced_pacer_pdf_downloader.py {case_event_id}")
    
    print("\n💡 ALTERNATIVE TEST:")
    print("If the enhanced downloader has issues, you can test with:")
    print(f"python single_case_event_pipeline.py {fk_case} {event_no} flsd")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_enhanced_downloader.py <case_event_id>")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    debug_enhanced_downloader(case_event_id)
