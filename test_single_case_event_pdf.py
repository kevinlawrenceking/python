#!/usr/bin/env python3
"""
Test Enhanced PDF Downloader on Single Case Event

PURPOSE:
Test the enhanced PDF downloader with a specific case event that
previously failed with "Cannot redisplay" error.

USAGE:
python test_single_case_event_pdf.py <case_event_id>

EXAMPLE:
python test_single_case_event_pdf.py 7CD5BD5C-7048-49A3-A495-FAE57A00EB42
"""

import sys
import subprocess
import pyodbc

def test_single_case_event_pdf(case_event_id):
    """Test enhanced PDF downloader on a specific case event"""
    
    print(f"🧪 TESTING ENHANCED PDF DOWNLOADER")
    print(f"Case Event ID: {case_event_id}")
    print("=" * 60)
    
    # First, check what documents are associated with this case event
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print("\n📋 CASE EVENT DETAILS:")
        print("-" * 30)
        
        # Get case event info
        cursor.execute("""
            SELECT ce.fk_cases, ce.event_no, c.case_name
            FROM docketwatch.dbo.case_events ce
            LEFT JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE ce.id = ?
        """, (case_event_id,))
        
        event_info = cursor.fetchone()
        if event_info:
            fk_case, event_no, case_name = event_info
            print(f"Case: {case_name}")
            print(f"Event Number: {event_no}")
            print(f"Case ID: {fk_case}")
        else:
            print(f"❌ Case event {case_event_id} not found")
            return False
        
        # Get documents for this case event
        cursor.execute("""
            SELECT id, pdf_url, status, error_message, rel_path
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
            ORDER BY id
        """, (case_event_id,))
        
        documents = cursor.fetchall()
        
        print(f"\n📄 DOCUMENTS ({len(documents)} found):")
        print("-" * 40)
        
        for doc_id, pdf_url, status, error_msg, rel_path in documents:
            print(f"Doc ID: {doc_id}")
            print(f"Status: {status}")
            print(f"URL: {pdf_url}")
            if error_msg:
                print(f"Error: {error_msg}")
            if rel_path:
                print(f"File: {rel_path}")
            print("-" * 40)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    # Now test the enhanced downloader
    print("\n🚀 RUNNING ENHANCED PDF DOWNLOADER:")
    print("-" * 40)
    
    try:
        # Run the enhanced downloader
        cmd = ["python", r"u:\docketwatch\python\enhanced_pacer_pdf_downloader.py", str(case_event_id)]
        
        print(f"Command: {' '.join(cmd)}")
        print("\nOutput:")
        
        # Run with real-time output
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(f"  {line.strip()}")
        
        process.wait()
        return_code = process.returncode
        
        print(f"\nReturn code: {return_code}")
        
        if return_code == 0:
            print("✅ Enhanced downloader completed successfully")
        else:
            print("⚠️ Enhanced downloader finished with warnings/errors")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to run enhanced downloader: {e}")
        return False

def check_results_after_test(case_event_id):
    """Check the results after running the test"""
    
    print("\n📊 POST-TEST RESULTS:")
    print("-" * 30)
    
    try:
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # Check document status after test
        cursor.execute("""
            SELECT id, status, error_message, rel_path, date_downloaded
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
            ORDER BY id
        """, (case_event_id,))
        
        documents = cursor.fetchall()
        
        downloaded_count = 0
        failed_count = 0
        pending_count = 0
        
        for doc_id, status, error_msg, rel_path, date_downloaded in documents:
            print(f"\nDoc {doc_id}:")
            print(f"  Status: {status}")
            
            if status == 'downloaded':
                downloaded_count += 1
                print(f"  ✅ File: {rel_path}")
                print(f"  📅 Downloaded: {date_downloaded}")
            elif status == 'failed':
                failed_count += 1
                print(f"  ❌ Error: {error_msg}")
            else:
                pending_count += 1
                print(f"  ⏳ Still pending")
        
        print(f"\n📈 SUMMARY:")
        print(f"  Downloaded: {downloaded_count}")
        print(f"  Failed: {failed_count}")
        print(f"  Pending: {pending_count}")
        
        if downloaded_count > 0:
            print(f"\n🎉 SUCCESS! Enhanced downloader resolved redisplay errors!")
        elif failed_count > 0:
            print(f"\n⚠️ Some documents still failed - check error messages above")
        else:
            print(f"\n⏳ Documents still pending - may need more time")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking results: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_single_case_event_pdf.py <case_event_id>")
        print("\nExample:")
        print("python test_single_case_event_pdf.py 7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    
    print("🎯 SINGLE CASE EVENT PDF DOWNLOAD TEST")
    print("=" * 50)
    
    # Run the test
    success = test_single_case_event_pdf(case_event_id)
    
    if success:
        # Check results
        check_results_after_test(case_event_id)
        
        print("\n💡 WHAT TO LOOK FOR:")
        print("• 'Redisplay error detected' = Enhanced downloader caught the error")
        print("• 'Fresh session created' = New browser session being used")
        print("• 'Alternative access' = Trying different download methods")
        print("• 'Successfully downloaded' = Problem solved!")
        
        print("\n📝 NEXT STEPS:")
        print("• If successful: Enhanced downloader is working correctly")
        print("• If failed: Check error messages for specific issues")
        print("• Monitor logs for detailed troubleshooting info")
    else:
        print("\n❌ Test setup failed - check case event ID and database connection")
