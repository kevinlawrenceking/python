#!/usr/bin/env python3
"""
Simple PACER PDF Download Test API
Backend script to handle PDF downloads from the HTML test page.
"""

import sys
import subprocess
import json
import os
import time
from urllib.parse import parse_qs
import cgi
import re

def log_message(message):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{timestamp} - {message}"

def validate_case_event_id(case_event_id):
    """Validate that the case event ID is a proper GUID format"""
    guid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    return re.match(guid_pattern, case_event_id) is not None

def run_pdf_download(case_event_id):
    """Run the lightweight enhanced downloader for the given case event ID"""
    
    if not validate_case_event_id(case_event_id):
        return {
            "success": False,
            "error": "Invalid case event ID format. Must be a valid GUID.",
            "output": ""
        }
    
    try:
        # Path to the lightweight enhanced downloader
        downloader_path = r"u:\docketwatch\python\lightweight_enhanced_downloader.py"
        
        if not os.path.exists(downloader_path):
            return {
                "success": False,
                "error": "Lightweight enhanced downloader script not found",
                "output": ""
            }
        
        # Build command
        cmd = ["python", downloader_path, case_event_id]
        
        # Run the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        # Combine stdout and stderr
        full_output = ""
        if result.stdout:
            full_output += result.stdout
        if result.stderr:
            if full_output:
                full_output += "\n--- STDERR ---\n"
            full_output += result.stderr
        
        return {
            "success": result.returncode == 0,
            "error": None if result.returncode == 0 else f"Process exited with code {result.returncode}",
            "output": full_output,
            "return_code": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Download process timed out after 10 minutes",
            "output": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error running download: {str(e)}",
            "output": ""
        }

def handle_request():
    """Handle the web request (GET or POST)"""
    
    # Set content type
    print("Content-Type: application/json")
    print()  # Empty line required between headers and content
    
    try:
        # Get the request method
        method = os.environ.get('REQUEST_METHOD', 'GET')
        
        if method == 'POST':
            # Handle POST request with form data
            form = cgi.FieldStorage()
            case_event_id = form.getvalue('case_event_id', '').strip()
        else:
            # Handle GET request with query parameters
            query_string = os.environ.get('QUERY_STRING', '')
            params = parse_qs(query_string)
            case_event_id = params.get('case_event_id', [''])[0].strip()
        
        if not case_event_id:
            result = {
                "success": False,
                "error": "No case event ID provided",
                "output": ""
            }
        else:
            result = run_pdf_download(case_event_id)
        
        # Return JSON response
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": f"Server error: {str(e)}",
            "output": ""
        }
        print(json.dumps(error_result, indent=2))

def run_cli():
    """Command line interface for direct testing"""
    if len(sys.argv) != 2:
        print("Usage: python simple_pacer_pdf_api.py <case_event_id>")
        print("\nExample:")
        print("python simple_pacer_pdf_api.py CC8013B7-EF21-428A-95A7-5053492BF184")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    
    print("🚀 SIMPLE PACER PDF DOWNLOAD TEST")
    print("=" * 50)
    print(f"Case Event ID: {case_event_id}")
    print("=" * 50)
    
    result = run_pdf_download(case_event_id)
    
    if result["success"]:
        print("\n✅ Download completed successfully!")
        print("\nOutput:")
        print(result["output"])
    else:
        print(f"\n❌ Download failed: {result['error']}")
        if result["output"]:
            print("\nOutput:")
            print(result["output"])

if __name__ == "__main__":
    # Check if running as CGI script or command line
    if os.environ.get('REQUEST_METHOD'):
        handle_request()
    else:
        run_cli()
