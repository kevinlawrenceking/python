"""
CLI wrapper for document summarization from uploaded files.
Supports --in (file path) and --extra (optional instructions).
Returns JSON output to stdout for consumption by CFML.
"""

import os
import sys
import json
import time
import argparse
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Redirect all regular output to stderr to keep stdout clean for JSON only
original_stdout = sys.stdout
sys.stdout = sys.stderr

# Try to import from existing summarizer, handle gracefully if it fails
try:
    from summarize_document_event import (
        pdf_to_text, clean_ocr_text, fix_encoding_garbage, normalize_quotes,
        extract_facts, render_summary, verify_summary, serialize_extraction,
        get_cursor, get_util, persist_guard_metadata, FACT_GUARD,
        refine_ocr_with_ai, BeautifulSoup, markdown2, parse_ai_summary,
        extraction_has_substance
    )
    IMPORTS_OK = True
except ImportError as e:
    IMPORTS_OK = False
    IMPORT_ERROR = str(e)

# Restore stdout for final JSON output
sys.stdout = original_stdout


def process_upload(file_path: str, extra_instructions: str = "") -> Dict[str, Any]:
    """
    Process an uploaded PDF file and return structured summary data.
    
    Args:
        file_path: Absolute path to PDF file
        extra_instructions: Optional additional instructions for summarization
        
    Returns:
        Dictionary with summary_text, summary_html, ocr_text, fields, etc.
    """
    
    # Check if imports succeeded
    if not IMPORTS_OK:
        return {
            "doc_uid": None,
            "model_name": "unknown",
            "summary_text": "Import error - dependencies not available",
            "summary_html": "<p>Import error - dependencies not available</p>",
            "ocr_text": "",
            "fields": {},
            "errors": [f"Import failed: {IMPORT_ERROR}"],
            "processing_ms": 0
        }
    
    t_start = time.time()
    result = {
        "doc_uid": None,
        "model_name": "gemini-2.5-flash",
        "summary_text": "",
        "summary_html": "",
        "ocr_text": "",
        "fields": {},
        "errors": [],
        "processing_ms": 0
    }
    
    try:
        # Validate file exists
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # No longer need API key - using service account
        conn, cur = get_cursor()
        
        # Extract text from PDF (try native, fall back to OCR)
        print("Extracting text from PDF...", file=sys.stderr)
        raw_text = pdf_to_text(file_path)
        ocr_text = clean_ocr_text(raw_text)
        
        # Optionally refine OCR with AI if text is poor quality
        if len(ocr_text.strip()) < 200 and len(ocr_text.strip()) > 0:
            print("Refining OCR with AI...", file=sys.stderr)
            try:
                ocr_text = refine_ocr_with_ai(ocr_text)  # No API key needed
            except Exception as e:
                print(f"OCR refinement failed: {e}", file=sys.stderr)
        
        result["ocr_text"] = ocr_text
        
        # Check if we have enough text to summarize
        if len(ocr_text.strip()) < 100:
            result["errors"].append("OCR text too short for meaningful summary")
            result["summary_text"] = "Document appears to be unreadable or contains insufficient text."
            result["summary_html"] = "<p>" + result["summary_text"] + "</p>"
            result["processing_ms"] = int((time.time() - t_start) * 1000)
            conn.close()
            return result
        
        # Build context for summarization
        case_overview = "Uploaded document for ad-hoc analysis"
        event_desc = "Document upload"
        event_date = datetime.now().strftime("%Y-%m-%d")
        
        # Append extra instructions if provided
        if extra_instructions:
            case_overview += f"\n\nAdditional instructions: {extra_instructions}"
        
        # Use FACT_GUARD pipeline if enabled
        if FACT_GUARD:
            print("Running FACT_GUARD extraction...", file=sys.stderr)
            
            # Step 1: Extract structured facts
            raw_extraction, extraction = extract_facts(
                ocr_text, case_overview, event_desc, event_date  # No API key needed
            )
            
            # Check if extraction has substance
            if not extraction_has_substance(extraction):
                result["errors"].append("Extraction produced no substantive facts")
                result["summary_text"] = "Unable to extract meaningful information from document."
                result["summary_html"] = "<p>" + result["summary_text"] + "</p>"
                result["fields"] = extraction
                result["processing_ms"] = int((time.time() - t_start) * 1000)
                conn.close()
                return result
            
            result["fields"] = extraction
            
            # Step 2: Render summary from extraction
            print("Rendering summary...", file=sys.stderr)
            summary_html = render_summary(extraction)  # No API key needed
            summary_html = fix_encoding_garbage(summary_html)
            summary_html = normalize_quotes(summary_html)
            
            # Step 3: Verify summary against extraction
            print("Verifying summary...", file=sys.stderr)
            passed, verdict = verify_summary(extraction, summary_html)  # No API key needed
            
            if not passed:
                result["errors"].append(f"Verification failed: {verdict}")
                print(f"Verification failed: {verdict}", file=sys.stderr)
                # Return anyway but mark as unverified
            
            result["summary_text"] = summary_html
            result["summary_html"] = BeautifulSoup(summary_html, "html.parser").prettify()
            result["verifier_result"] = "PASSED" if passed else "FAILED"
            result["verifier_notes"] = None if passed else verdict
            
        else:
            # Legacy single-shot summarization
            print("Running single-shot summarization...", file=sys.stderr)
            from summarize_document_event import ask_gemini
            
            summary_text = ask_gemini(case_overview, event_desc, event_date, ocr_text)  # No API key needed
            summary_text = fix_encoding_garbage(summary_text)
            summary_text = normalize_quotes(summary_text)
            
            result["summary_text"] = summary_text
            result["summary_html"] = BeautifulSoup(
                markdown2.markdown(summary_text), "html.parser"
            ).prettify()
            
            # Try to parse fields from summary
            parsed = parse_ai_summary(summary_text)
            if parsed:
                result["fields"] = parsed
        
        result["processing_ms"] = int((time.time() - t_start) * 1000)
        conn.close()
        
        print(f"Processing completed in {result['processing_ms']}ms", file=sys.stderr)
        return result
        
    except Exception as e:
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {str(e)}"
        result["errors"].append(error_msg)
        result["summary_text"] = f"Error processing document: {error_msg}"
        result["summary_html"] = f"<p>Error processing document: {error_msg}</p>"
        result["processing_ms"] = int((time.time() - t_start) * 1000)
        
        print(f"Error: {error_msg}", file=sys.stderr)
        print(tb, file=sys.stderr)
        
        return result


def main():
    """Main CLI entry point."""
    # Keep stdout redirected to stderr during argument parsing
    temp_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    parser = argparse.ArgumentParser(
        description="Process PDF upload and generate AI summary"
    )
    parser.add_argument(
        "--in", dest="infile", required=True,
        help="Path to PDF file to process"
    )
    parser.add_argument(
        "--extra", default="",
        help="Optional extra instructions for summarization"
    )
    
    args = parser.parse_args()
    
    try:
        # Process the file (output to stderr)
        result = process_upload(args.infile, args.extra)
        
        # Restore stdout ONLY for JSON output
        sys.stdout = temp_stdout
        
        # Output JSON to stdout (consumed by CFML)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        # Even on catastrophic failure, return valid JSON
        tb = traceback.format_exc()
        error_result = {
            "doc_uid": None,
            "model_name": "unknown",
            "summary_text": f"Fatal error: {str(e)}",
            "summary_html": f"<p>Fatal error: {str(e)}</p>",
            "ocr_text": "",
            "fields": {},
            "errors": [f"{type(e).__name__}: {str(e)}"],
            "processing_ms": 0,
            "traceback": tb
        }
        
        # Restore stdout for JSON error output
        sys.stdout = temp_stdout
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
