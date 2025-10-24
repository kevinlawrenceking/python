"""
Test the extraction JSON parsing improvements.
This tests the fix for truncated/malformed JSON responses.
"""

import json
import sys
import pyodbc
from summarize_document_event import (
    extract_facts, auto_close_json, get_cursor, get_util
)


def test_auto_close_json():
    """Test the JSON auto-close repair function."""
    print("Testing auto_close_json()...")
    
    # Test 1: Truncated object (complete string values)
    truncated1 = '{"name": "test", "value": 123, "nested": {"key": "val'
    closed1 = auto_close_json(truncated1)
    print(f"Test 1 - Truncated object with incomplete string:")
    print(f"  Input:  {truncated1}")
    print(f"  Output: {closed1}")
    try:
        result = json.loads(closed1)
        print(f"  ✓ Valid JSON - nested.key = {result['nested']['key']}")
    except Exception as e:
        print(f"  ✗ Invalid JSON: {e}")
    
    # Test 2: Truncated at comma (better scenario)
    truncated2 = '{"items": [1, 2, 3], "data": {"status": "pending'
    closed2 = auto_close_json(truncated2)
    print(f"\nTest 2 - Truncated at string end:")
    print(f"  Input:  {truncated2}")
    print(f"  Output: {closed2}")
    try:
        result = json.loads(closed2)
        print(f"  ✓ Valid JSON - data.status = {result['data']['status']}")
    except Exception as e:
        print(f"  ✗ Invalid JSON: {e}")
    
    # Test 3: Complete fields but missing closing braces
    truncated3 = '{"a": "value1", "b": {"c": "value2", "d": [1, 2, 3'
    closed3 = auto_close_json(truncated3)
    print(f"\nTest 3 - Missing closing brackets:")
    print(f"  Input:  {truncated3}")
    print(f"  Output: {closed3}")
    try:
        result = json.loads(closed3)
        print(f"  ✓ Valid JSON - b.d = {result['b']['d']}")
    except Exception as e:
        print(f"  ✗ Invalid JSON: {e}")
    
    # Test 4: Real-world scenario - response cut off after complete field
    truncated4 = '{"doc_type": "Order", "filing_date_iso": "2025-09-08", "parties": {"plaintiff": "Anna Kane", "defendant": "Sean Combs"'
    closed4 = auto_close_json(truncated4)
    print(f"\nTest 4 - Real-world truncation (cut off after name):")
    print(f"  Input:  {truncated4[:80]}...")
    print(f"  Output: {closed4[:80]}...")
    try:
        result = json.loads(closed4)
        print(f"  ✓ Valid JSON - parties.plaintiff = {result['parties']['plaintiff']}")
    except Exception as e:
        print(f"  ✗ Invalid JSON: {e}")
    
    print("\nNOTE: Some truncation scenarios cannot be perfectly repaired,")
    print("but the function attempts best-effort recovery to extract partial data.")
    print("\n" + "="*60 + "\n")


def test_extraction_with_real_doc():
    """Test extraction with a real document from database."""
    print("Testing extraction with real document...")
    
    conn, cur = get_cursor()
    api_key = get_util(cur, "gemini_api")
    
    if not api_key:
        print("❌ No Gemini API key found in database")
        return
    
    # Get a recent document with OCR text
    cur.execute("""
        SELECT TOP 1 
            doc_uid, 
            ocr_text,
            fk_case
        FROM docketwatch.dbo.documents
        WHERE ocr_text IS NOT NULL
          AND LEN(ocr_text) > 500
          AND pdf_type = 'Docket'
        ORDER BY date_downloaded DESC
    """)
    
    row = cur.fetchone()
    if not row:
        print("❌ No suitable document found")
        conn.close()
        return
    
    doc_uid = str(row.doc_uid)
    ocr_text = row.ocr_text[:5000]  # Limit for testing
    
    # Get case overview
    cur.execute("""
        SELECT summarize
        FROM docketwatch.dbo.cases
        WHERE id = ?
    """, (row.fk_case,))
    
    case_row = cur.fetchone()
    case_overview = case_row.summarize if case_row else "Unknown case"
    
    print(f"\nDocument: {doc_uid}")
    print(f"OCR text length: {len(ocr_text)}")
    print(f"Case overview: {case_overview[:100]}...")
    print("\nAttempting extraction...")
    
    try:
        raw_json, extraction = extract_facts(
            pdf_text=ocr_text,
            case_overview=case_overview or "Unknown case",
            event_desc="Test extraction",
            event_date="2025-10-22",
            api_key=api_key,
            doc_uid=doc_uid
        )
        
        print("✓ Extraction succeeded!")
        print(f"\nExtracted fields:")
        print(f"  doc_type: {extraction.get('doc_type')}")
        print(f"  filing_action_summary: {extraction.get('filing_action_summary', '')[:100]}...")
        print(f"  parties: {extraction.get('parties', {})}")
        print(f"  newsworthiness: {extraction.get('newsworthiness')}")
        
        print(f"\nRaw JSON length: {len(raw_json)} chars")
        print(f"Extraction dict keys: {len(extraction)} keys")
        
    except ValueError as e:
        print(f"✗ Extraction failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    conn.close()
    print("\n" + "="*60 + "\n")


def main():
    print("\n" + "="*60)
    print("EXTRACTION JSON PARSING FIX TEST")
    print("="*60 + "\n")
    
    # Test 1: JSON repair functions
    test_auto_close_json()
    
    # Test 2: Real extraction (optional - requires API call)
    if "--full" in sys.argv:
        test_extraction_with_real_doc()
    else:
        print("Skipping real extraction test (use --full to enable)")
        print("This avoids using API quota during development")
    
    print("\nAll tests complete!")


if __name__ == "__main__":
    main()
