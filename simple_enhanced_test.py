#!/usr/bin/env python3
"""
Simple Enhanced PDF Downloader Test

PURPOSE:
Run the enhanced PDF downloader directly on the Pete v. Cooper case
without complex database queries that depend on unknown schema.
"""

import subprocess
import sys

def simple_enhanced_test(case_event_id):
    """Run enhanced downloader directly and show output"""
    
    print("🎯 SIMPLE ENHANCED PDF DOWNLOADER TEST")
    print(f"Case Event ID: {case_event_id}")
    print("=" * 60)
    
    print(f"\n✅ Case Event Found: Pete v. Cooper (Event 138)")
    print(f"✅ Enhanced downloader available")
    
    print(f"\n🚀 RUNNING ENHANCED PDF DOWNLOADER:")
    print("-" * 40)
    
    try:
        # Run the enhanced downloader directly
        cmd = ["python", "enhanced_pacer_pdf_downloader.py", str(case_event_id)]
        
        print(f"Command: {' '.join(cmd)}")
        print(f"\n📋 Output:")
        print("-" * 20)
        
        # Run with real-time output
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Show output
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nReturn code: {result.returncode}")
        
        if result.returncode == 0:
            print("\n✅ Enhanced downloader completed successfully!")
            print("\n🔍 WHAT TO LOOK FOR IN THE OUTPUT:")
            print("• 'Enhanced PACER PDF Downloader starting' = Started correctly")
            print("• 'Found X pending documents' = Documents to process")
            print("• 'Redisplay error detected' = Found the problem")
            print("• 'Creating fresh session' = Applying solution")
            print("• 'Successfully downloaded' = Problem solved!")
        else:
            print(f"\n⚠️ Enhanced downloader finished with return code {result.returncode}")
            print("Check the output above for specific errors")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Enhanced downloader timed out (>5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Failed to run enhanced downloader: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python simple_enhanced_test.py <case_event_id>")
        print("\nFor Pete v. Cooper case:")
        print("python simple_enhanced_test.py 7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    
    print("🧪 TESTING ENHANCED PDF DOWNLOADER ON SINGLE CASE")
    print("=" * 55)
    
    success = simple_enhanced_test(case_event_id)
    
    if success:
        print("\n📊 NEXT STEPS:")
        print("1. Review the output above for 'redisplay error' messages")
        print("2. Check if any PDFs were successfully downloaded")
        print("3. Look for 'alternative method' success messages")
        print("4. Monitor your file system for new PDF files")
        
        print("\n💡 SUCCESS INDICATORS:")
        print("✅ 'Document X successfully downloaded' = Working!")
        print("✅ 'Enhanced downloader completed' = No crashes")
        print("⚠️ 'Redisplay error detected' + 'alternative method' = Fix applied")
    else:
        print("\n❌ Test failed - check the error messages above")
