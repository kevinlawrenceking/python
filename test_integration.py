"""
Test script for the integrated DocketWatch unfiled scraper with PDF downloading.
This script tests the integration without processing real data.
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

def test_integration():
    """
    Test the integrated unfiled scraper with a recent date.
    This will process real data but with limited scope for testing.
    """
    
    # Get yesterday's date for testing
    yesterday = datetime.now() - timedelta(days=1)
    test_date = yesterday.strftime('%Y-%m-%d')
    
    print(f"Testing integrated unfiled scraper for date: {test_date}")
    print("This will process real unfiled records with PDF downloading integration.")
    print()
    
    # Confirm before proceeding
    response = input("Do you want to proceed with the test? (y/N): ").strip().lower()
    if response != 'y':
        print("Test cancelled.")
        return
    
    try:
        # Run the integrated script
        script_path = os.path.join(os.path.dirname(__file__), "docketwatch_map_unfiled_scraper.py")
        
        print(f"Running: python {script_path} {test_date}")
        print("=" * 60)
        
        result = subprocess.run(
            [sys.executable, script_path, test_date],
            capture_output=False,  # Show output in real-time
            text=True
        )
        
        print("=" * 60)
        if result.returncode == 0:
            print("✓ Test completed successfully!")
            print("Check the logs and database to verify:")
            print("1. New unfiled records have associated PDFs")
            print("2. No orphaned records without PDFs")
            print("3. Document records were created")
        else:
            print(f"✗ Test failed with return code: {result.returncode}")
            
    except Exception as e:
        print(f"✗ Test exception: {e}")

def check_dependencies():
    """Check if required dependencies are available."""
    
    print("Checking dependencies...")
    
    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js: {result.stdout.strip()}")
        else:
            print("✗ Node.js not found")
            return False
    except FileNotFoundError:
        print("✗ Node.js not found")
        return False
    
    # Check if download_map_filing.js exists
    js_script = os.path.join(os.path.dirname(__file__), "download_map_filing.js")
    if os.path.exists(js_script):
        print("✓ download_map_filing.js found")
    else:
        print("✗ download_map_filing.js not found")
        return False
    
    # Check if combine_images_to_pdf.py exists
    py_script = os.path.join(os.path.dirname(__file__), "combine_images_to_pdf.py")
    if os.path.exists(py_script):
        print("✓ combine_images_to_pdf.py found")
    else:
        print("✗ combine_images_to_pdf.py not found")
        return False
    
    # Check Python packages
    try:
        import requests
        import selenium
        import pyodbc
        from PIL import Image
        from reportlab.pdfgen import canvas
        print("✓ Required Python packages available")
    except ImportError as e:
        print(f"✗ Missing Python package: {e}")
        return False
    
    print("✓ All dependencies check passed")
    return True

if __name__ == "__main__":
    print("DocketWatch Integration Test")
    print("=" * 40)
    
    if check_dependencies():
        print()
        test_integration()
    else:
        print("\n✗ Dependency check failed. Please install missing dependencies.")
