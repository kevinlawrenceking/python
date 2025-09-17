#!/usr/bin/env python3
"""
PACER PDF Processor
Downloads PDFs from PACER URLs and saves them to the specified location.
Returns JSON responses for ColdFusion integration.
"""

import sys
import json
import requests
import os
from urllib.parse import urlparse
from pathlib import Path

def download_pdf(url, output_path):
    """
    Download a PDF from the given URL and save it to output_path.
    Returns a dict with status and message.
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Set up headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Download the file
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        # Check if the response is actually a PDF
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' not in content_type and 'octet-stream' not in content_type:
            return {
                'status': 'error',
                'message': f'URL did not return a PDF. Content-Type: {content_type}'
            }
        
        # Save the file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify the file was created and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {
                'status': 'success',
                'message': f'PDF downloaded successfully to {output_path}',
                'file_size': os.path.getsize(output_path)
            }
        else:
            return {
                'status': 'error',
                'message': 'File was not created or is empty'
            }
            
    except requests.exceptions.RequestException as e:
        return {
            'status': 'error',
            'message': f'Network error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Unexpected error: {str(e)}'
        }

def main():
    """Main function that handles command line arguments and returns JSON response."""
    if len(sys.argv) != 3:
        result = {
            'status': 'error',
            'message': 'Usage: python combined_pacer_pdf_processor.py <url> <output_path>'
        }
        print(json.dumps(result))
        sys.exit(1)
    
    url = sys.argv[1]
    output_path = sys.argv[2]
    
    # Validate URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            result = {
                'status': 'error',
                'message': 'Invalid URL format'
            }
            print(json.dumps(result))
            sys.exit(1)
    except Exception as e:
        result = {
            'status': 'error',
            'message': f'URL validation error: {str(e)}'
        }
        print(json.dumps(result))
        sys.exit(1)
    
    # Download the PDF
    result = download_pdf(url, output_path)
    print(json.dumps(result))
    
    # Exit with appropriate code
    sys.exit(0 if result['status'] == 'success' else 1)

if __name__ == '__main__':
    main()