"""
Setup verification script for AI Summary Upload Tool.
Checks all prerequisites and reports any missing components.
"""

import os
import sys
import importlib

def check_python_version():
    """Verify Python 3.12+ is installed."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 12:
        print(f"✓ Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python version {version.major}.{version.minor} is too old (need 3.12+)")
        return False

def check_dependencies():
    """Check if all required Python packages are installed."""
    required = [
        'google.generativeai',
        'PyPDF2',
        'pdf2image',
        'pytesseract',
        'cv2',  # opencv-python
        'pyodbc',
        'bs4',  # beautifulsoup4
        'markdown2'
    ]
    
    missing = []
    for package in required:
        try:
            importlib.import_module(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - NOT INSTALLED")
            missing.append(package)
    
    return len(missing) == 0, missing

def check_directories():
    """Verify required directories exist."""
    dirs = [
        "U:\\docketwatch\\uploads",
        "U:\\docketwatch\\python",
        "U:\\docketwatch\\python\\logs",
        "U:\\docketwatch\\court-beta\\tools",
        "U:\\docketwatch\\court-beta\\ajax"
    ]
    
    all_exist = True
    for dir_path in dirs:
        if os.path.isdir(dir_path):
            print(f"✓ {dir_path}")
        else:
            print(f"✗ {dir_path} - MISSING")
            all_exist = False
    
    return all_exist

def check_files():
    """Verify required files exist."""
    files = [
        "U:\\docketwatch\\python\\summarize_upload_cli.py",
        "U:\\docketwatch\\python\\summarize_document_event.py",
        "U:\\docketwatch\\court-beta\\tools\\summarize_upload.cfm",
        "U:\\docketwatch\\court-beta\\ajax\\upload_and_summarize.cfm",
        "U:\\docketwatch\\court-beta\\ajax\\save_qc_feedback.cfm"
    ]
    
    all_exist = True
    for file_path in files:
        if os.path.isfile(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - MISSING")
            all_exist = False
    
    return all_exist

def check_database_connection():
    """Test database connectivity."""
    try:
        import pyodbc
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        # Check if utilities table exists and has gemini_api
        cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        
        if row and row[0]:
            print("✓ Database connection OK")
            print("✓ Gemini API key configured")
            conn.close()
            return True
        else:
            print("✗ Gemini API key not found in utilities table")
            conn.close()
            return False
            
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def main():
    """Run all checks and report results."""
    print("=" * 60)
    print("AI Summary Upload Tool - Setup Verification")
    print("=" * 60)
    
    all_good = True
    
    print("\n1. Python Version:")
    print("-" * 40)
    if not check_python_version():
        all_good = False
    
    print("\n2. Python Dependencies:")
    print("-" * 40)
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        all_good = False
        print(f"\nTo install missing packages:")
        print(f"pip install {' '.join(missing)}")
    
    print("\n3. Required Directories:")
    print("-" * 40)
    if not check_directories():
        all_good = False
    
    print("\n4. Required Files:")
    print("-" * 40)
    if not check_files():
        all_good = False
    
    print("\n5. Database Connection:")
    print("-" * 40)
    if not check_database_connection():
        all_good = False
    
    print("\n" + "=" * 60)
    if all_good:
        print("✓ ALL CHECKS PASSED - System is ready!")
    else:
        print("✗ SOME CHECKS FAILED - Please fix the issues above")
    print("=" * 60)
    
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
