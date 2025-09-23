#!/usr/bin/env python3
"""
PACER PDF Download Wrapper

This script provides a drop-in replacement for extract_pacer_pdf_file.py
that uses the enhanced downloader to fix the PDF extraction issues.

It maintains the same interface while using improved download logic.
"""

import sys
import subprocess
import os

def main():
    if len(sys.argv) != 2:
        print("Usage: python pacer_pdf_download_wrapper.py <case_event_id>")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    
    print(f"PACER PDF Download Wrapper starting for case event: {case_event_id}")
    
    # Try the enhanced extractor first
    enhanced_script = os.path.join(os.path.dirname(__file__), "enhanced_pacer_pdf_extractor.py")
    
    try:
        result = subprocess.run([
            "C:/Python312/python.exe",
            enhanced_script,
            case_event_id
        ], capture_output=True, text=True, timeout=600)  # 10 minute timeout
        
        if result.returncode == 0:
            print("✅ Enhanced PDF extractor completed successfully")
            print(result.stdout)
            return 0
        else:
            print("❌ Enhanced PDF extractor failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            
            # Fallback to original extractor
            print("Attempting fallback to original extractor...")
            original_script = os.path.join(os.path.dirname(__file__), "extract_pacer_pdf_file.py")
            
            fallback_result = subprocess.run([
                "C:/Python312/python.exe",
                original_script,
                case_event_id
            ], capture_output=True, text=True, timeout=600)
            
            if fallback_result.returncode == 0:
                print("✅ Fallback extractor completed successfully")
                print(fallback_result.stdout)
                return 0
            else:
                print("❌ Both extractors failed")
                print("Fallback STDOUT:", fallback_result.stdout)
                print("Fallback STDERR:", fallback_result.stderr)
                return 1
                
    except subprocess.TimeoutExpired:
        print("❌ PDF extraction timed out")
        return 1
    except Exception as e:
        print(f"❌ Error running PDF extractor: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())