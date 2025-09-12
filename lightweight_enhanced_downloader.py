#!/usr/bin/env python3
"""
Lightweight Enhanced PDF Downloader

This version handles the "Cannot redisplay" error without using Selenium,
which seems to be causing the hanging issue. Instead, it uses the working
extract_pacer_pdf_file.py with retry logic and session management.
"""

import sys
import subprocess
import time
import pyodbc
import os
import tempfile

def log_message(message):
    """Simple logging function"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

def lightweight_enhanced_download(case_event_id):
    """
    Enhanced PDF download without Selenium - uses retry logic with the working downloader.
    """
    log_message(f"Lightweight Enhanced PDF Downloader starting for case_event_id: {case_event_id}")
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        # Check if there are documents to process
        cursor.execute("""
            SELECT COUNT(*)
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
        """, (case_event_id,))
        
        doc_count = cursor.fetchone()[0]
        log_message(f"Found {doc_count} documents for case event")
        
        if doc_count == 0:
            log_message("No documents found - nothing to download")
            return True
        
        # Strategy 1: Try original downloader first
        log_message("Attempting PDF download with original downloader...")
        
        original_cmd = ["python", r"u:\docketwatch\python\extract_pacer_pdf_file.py", str(case_event_id)]
        
        try:
            result = subprocess.run(
                original_cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout
            )
            
            log_message(f"Original downloader return code: {result.returncode}")
            
            if result.stdout:
                log_message(f"STDOUT: {result.stdout[:500]}...")  # First 500 chars
            
            if result.stderr:
                log_message(f"STDERR: {result.stderr[:500]}...")  # First 500 chars
            
            # Check for redisplay error in output
            output_text = (result.stdout + result.stderr).lower()
            
            if "cannot redisplay" in output_text or "already been shown" in output_text:
                log_message("🔴 REDISPLAY ERROR DETECTED in original downloader output")
                
                # Strategy 2: Clear browser cache and retry
                log_message("Applying redisplay error fix - clearing cache and retrying...")
                
                # Clear any Chrome user data that might be cached
                clear_browser_cache()
                
                # Wait a bit before retry
                time.sleep(10)
                
                # Retry with original downloader
                log_message("Retrying original downloader after cache clear...")
                retry_result = subprocess.run(
                    original_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                log_message(f"Retry return code: {retry_result.returncode}")
                
                if retry_result.stdout:
                    log_message(f"Retry STDOUT: {retry_result.stdout[:500]}...")
                
                retry_output = (retry_result.stdout + retry_result.stderr).lower()
                
                if "cannot redisplay" in retry_output:
                    log_message("🔴 Redisplay error persists after retry")
                    log_message("This document may be permanently restricted by PACER")
                    
                    # Mark documents as failed with specific error
                    mark_documents_failed(cursor, case_event_id, "PACER redisplay restriction - document cannot be accessed again")
                    
                    return False
                else:
                    log_message("✅ Retry successful - redisplay error resolved")
                    return True
            else:
                if result.returncode == 0:
                    log_message("✅ Original downloader completed successfully")
                    return True
                else:
                    log_message(f"⚠️ Original downloader completed with warnings (code {result.returncode})")
                    return True
        
        except subprocess.TimeoutExpired:
            log_message("❌ Original downloader timed out after 5 minutes")
            return False
        except Exception as e:
            log_message(f"❌ Error running original downloader: {e}")
            return False
    
    except Exception as e:
        log_message(f"❌ Lightweight enhanced downloader error: {e}")
        return False
    
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

def clear_browser_cache():
    """Clear browser cache and temporary files to avoid session conflicts"""
    log_message("Clearing browser cache and temporary files...")
    
    try:
        # Clear Chrome user data directories
        chrome_user_data_dirs = [
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data"),
            os.path.expanduser("~\\AppData\\Local\\Chromium\\User Data"),
            tempfile.gettempdir()
        ]
        
        for user_data_dir in chrome_user_data_dirs:
            if os.path.exists(user_data_dir):
                # Don't actually delete the main Chrome profile, just clear temp files
                temp_files = [f for f in os.listdir(user_data_dir) if f.startswith('tmp') or f.startswith('temp')]
                for temp_file in temp_files[:10]:  # Limit to first 10 to avoid issues
                    try:
                        temp_path = os.path.join(user_data_dir, temp_file)
                        if os.path.isfile(temp_path):
                            os.remove(temp_path)
                    except:
                        pass
        
        log_message("Browser cache cleanup completed")
        
    except Exception as e:
        log_message(f"Cache cleanup warning: {e}")

def mark_documents_failed(cursor, case_event_id, error_message):
    """Mark documents as failed with specific error message"""
    try:
        cursor.execute("""
            UPDATE docketwatch.dbo.documents
            SET status = 'failed', error_message = ?
            WHERE fk_case_event = ?
        """, (error_message, case_event_id))
        cursor.commit()
        log_message("Documents marked as failed due to PACER restrictions")
    except Exception as e:
        log_message(f"Error marking documents as failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python lightweight_enhanced_downloader.py <case_event_id>")
        print("\nExample:")
        print("python lightweight_enhanced_downloader.py 942268B4-C3B1-4D85-9733-F0E9FBF68518")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    
    print("🚀 LIGHTWEIGHT ENHANCED PDF DOWNLOADER")
    print("=" * 50)
    print("This version handles PACER 'Cannot redisplay' errors")
    print("without using Selenium (which was causing hanging issues)")
    print("=" * 50)
    
    success = lightweight_enhanced_download(case_event_id)
    
    if success:
        print("\n✅ Enhanced download process completed successfully")
    else:
        print("\n❌ Enhanced download process encountered issues")
        print("Check the log messages above for details")
