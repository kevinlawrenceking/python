#!/usr/bin/env python3
"""
PACER PDF Download Diagnostic Tool

This script helps diagnose and fix issues with PACER PDF downloads.
It analyzes the current state and provides recommendations.
"""

import pyodbc
import os
import sys
import glob
from datetime import datetime, timedelta

def check_database_status():
    """Check database for pending downloads and recent failures"""
    print("🔍 CHECKING DATABASE STATUS")
    print("=" * 50)
    
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        # Check pending documents
        cursor.execute("""
            SELECT COUNT(*) as pending_count
            FROM docketwatch.dbo.documents 
            WHERE rel_path = 'pending'
        """)
        pending_count = cursor.fetchone()[0]
        print(f"📄 Pending documents: {pending_count}")
        
        # Check recent downloads
        cursor.execute("""
            SELECT COUNT(*) as recent_downloads
            FROM docketwatch.dbo.documents 
            WHERE date_downloaded >= DATEADD(hour, -24, GETDATE())
            AND rel_path IS NOT NULL AND rel_path != 'pending'
        """)
        recent_downloads = cursor.fetchone()[0]
        print(f"⬇️  Downloads in last 24 hours: {recent_downloads}")
        
        # Check failed attempts (documents that have been pending for too long)
        cursor.execute("""
            SELECT COUNT(*) as stale_pending
            FROM docketwatch.dbo.documents d
            INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
            WHERE d.rel_path = 'pending'
            AND ce.created_at < DATEADD(hour, -2, GETDATE())
        """)
        stale_pending = cursor.fetchone()[0]
        print(f"⚠️  Stale pending documents (>2 hours): {stale_pending}")
        
        # Show some examples of recent failures
        if stale_pending > 0:
            print("\n🔍 Recent problem documents:")
            cursor.execute("""
                SELECT TOP 5 
                    d.doc_id,
                    d.pdf_url,
                    c.case_name,
                    ce.event_description
                FROM docketwatch.dbo.documents d
                INNER JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
                INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
                WHERE d.rel_path = 'pending'
                AND ce.created_at < DATEADD(hour, -2, GETDATE())
                ORDER BY ce.created_at DESC
            """)
            
            for row in cursor.fetchall():
                doc_id, pdf_url, case_name, event_desc = row
                print(f"   📋 Doc {doc_id}: {case_name[:40]}...")
                print(f"      URL: {pdf_url}")
                print(f"      Event: {event_desc[:60]}...")
                print()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")

def check_file_system():
    """Check file system for PDF storage issues"""
    print("\n🗂️  CHECKING FILE SYSTEM")
    print("=" * 50)
    
    docs_root = r"\\10.146.176.84\general\docketwatch\docs\cases"
    
    if not os.path.exists(docs_root):
        print(f"❌ Documents root directory not accessible: {docs_root}")
        return
    
    print(f"✅ Documents root accessible: {docs_root}")
    
    # Check recent PDFs
    recent_pdfs = []
    try:
        for root, dirs, files in os.walk(docs_root):
            for file in files:
                if file.endswith('.pdf'):
                    filepath = os.path.join(root, file)
                    mtime = os.path.getmtime(filepath)
                    if mtime > (datetime.now() - timedelta(hours=24)).timestamp():
                        recent_pdfs.append((filepath, mtime))
        
        recent_pdfs.sort(key=lambda x: x[1], reverse=True)
        print(f"📄 PDFs created in last 24 hours: {len(recent_pdfs)}")
        
        if recent_pdfs:
            print("\n🕒 Most recent PDFs:")
            for filepath, mtime in recent_pdfs[:5]:
                size = os.path.getsize(filepath)
                mod_time = datetime.fromtimestamp(mtime)
                print(f"   {os.path.basename(filepath)} - {size:,} bytes - {mod_time}")
    
    except Exception as e:
        print(f"⚠️  Error scanning PDF files: {e}")

def check_chrome_setup():
    """Check Chrome and WebDriver setup"""
    print("\n🌐 CHECKING CHROME SETUP")
    print("=" * 50)
    
    chromedriver_path = "C:/WebDriver/chromedriver.exe"
    
    if os.path.exists(chromedriver_path):
        print(f"✅ ChromeDriver found: {chromedriver_path}")
    else:
        print(f"❌ ChromeDriver not found: {chromedriver_path}")
    
    # Check for Chrome installation
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    
    chrome_found = False
    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            print(f"✅ Chrome found: {chrome_path}")
            chrome_found = True
            break
    
    if not chrome_found:
        print("❌ Chrome browser not found in standard locations")

def analyze_recent_logs():
    """Analyze recent log files for patterns"""
    print("\n📊 ANALYZING RECENT LOGS")
    print("=" * 50)
    
    log_dir = r"\\10.146.176.84\general\docketwatch\python\logs"
    
    if not os.path.exists(log_dir):
        print(f"❌ Log directory not accessible: {log_dir}")
        return
    
    # Look for recent extract_pacer_pdf_file logs
    log_pattern = os.path.join(log_dir, "extract_pacer_pdf_file*.log")
    log_files = glob.glob(log_pattern)
    
    if not log_files:
        print("⚠️  No extract_pacer_pdf_file log files found")
        return
    
    # Get the most recent log file
    latest_log = max(log_files, key=os.path.getmtime)
    print(f"📋 Analyzing latest log: {os.path.basename(latest_log)}")
    
    try:
        with open(latest_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Count different types of messages
        error_count = sum(1 for line in lines if " - ERROR - " in line)
        warning_count = sum(1 for line in lines if " - WARNING - " in line)
        success_count = sum(1 for line in lines if "PDF saved successfully" in line)
        html_instead_pdf = sum(1 for line in lines if "Still getting HTML page instead of PDF" in line)
        billing_pages = sum(1 for line in lines if "PACER billing confirmation page detected" in line)
        
        print(f"📈 Log analysis:")
        print(f"   ✅ Successful downloads: {success_count}")
        print(f"   ❌ Errors: {error_count}")
        print(f"   ⚠️  Warnings: {warning_count}")
        print(f"   🌐 HTML instead of PDF: {html_instead_pdf}")
        print(f"   💰 Billing pages encountered: {billing_pages}")
        
        if html_instead_pdf > 0:
            print(f"\n🎯 MAIN ISSUE IDENTIFIED: Getting HTML instead of PDF content")
            print("   This suggests PACER is not serving the PDF correctly")
            print("   Recommendation: Use enhanced PDF extractor with browser downloads")
        
        # Show recent errors
        if error_count > 0:
            print(f"\n🔍 Recent errors:")
            for line in lines[-50:]:  # Last 50 lines
                if " - ERROR - " in line:
                    print(f"   {line.strip()}")
    
    except Exception as e:
        print(f"⚠️  Error reading log file: {e}")

def provide_recommendations():
    """Provide specific recommendations based on analysis"""
    print("\n💡 RECOMMENDATIONS")
    print("=" * 50)
    
    print("1. 🔧 IMMEDIATE FIXES:")
    print("   • Use enhanced_pacer_pdf_extractor.py instead of extract_pacer_pdf_file.py")
    print("   • The enhanced version uses browser downloads instead of URL extraction")
    print("   • This bypasses PACER's 'show_temp.pl' URL issues")
    
    print("\n2. 🔄 WORKFLOW UPDATES:")
    print("   • Update RSS trigger to use enhanced extractor")
    print("   • Use pacer_pdf_download_wrapper.py for automatic fallback")
    print("   • Monitor logs for 'PDF downloaded successfully' messages")
    
    print("\n3. 🚀 TESTING:")
    print("   • Test with a known failing case event:")
    print("     python enhanced_pacer_pdf_extractor.py <case_event_id>")
    print("   • Check download directory for completed files")
    print("   • Verify database updates")
    
    print("\n4. 📊 MONITORING:")
    print("   • Watch for 'Still getting HTML page instead of PDF' messages")
    print("   • Monitor pending document counts")
    print("   • Check for stale pending documents daily")

def main():
    print("🔧 PACER PDF DOWNLOAD DIAGNOSTIC TOOL")
    print("=" * 60)
    print(f"Diagnostic run at: {datetime.now()}")
    print()
    
    check_database_status()
    check_file_system()
    check_chrome_setup()
    analyze_recent_logs()
    provide_recommendations()
    
    print("\n" + "=" * 60)
    print("✅ Diagnostic complete!")
    print("📧 Share this output with the development team for troubleshooting")

if __name__ == "__main__":
    main()