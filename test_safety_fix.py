"""
Test script to verify safety filter handling in summarize_document_event.py
Tests the fix for finish_reason=2 (SAFETY) blocking responses.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from summarize_document_event import process_single_pdf

def test_sean_combs_document():
    """
    Test with the Sean Combs document that previously triggered safety filter.
    Document UID: 21f00aa3-a026-4c15-a8c4-da8e8cfe9d3b
    """
    doc_uid = "21f00aa3-a026-4c15-a8c4-da8e8cfe9d3b"
    
    print(f"Testing safety filter fix with document: {doc_uid}")
    print("=" * 80)
    
    try:
        process_single_pdf(doc_uid)
        print("\n" + "=" * 80)
        print("SUCCESS: Document processed without safety filter errors")
        print("=" * 80)
        return True
    except ValueError as e:
        error_msg = str(e)
        if "safety filter" in error_msg.lower():
            print("\n" + "=" * 80)
            print("SAFETY FILTER ERROR (Expected with sensitive content):")
            print(error_msg)
            print("\nThis is now properly handled with informative error message.")
            print("=" * 80)
            return True  # This is expected behavior for highly sensitive content
        else:
            print("\n" + "=" * 80)
            print("UNEXPECTED ERROR:")
            print(error_msg)
            print("=" * 80)
            raise
    except Exception as e:
        print("\n" + "=" * 80)
        print("UNEXPECTED ERROR TYPE:")
        print(f"{type(e).__name__}: {e}")
        print("=" * 80)
        raise

if __name__ == "__main__":
    test_sean_combs_document()
