#!/usr/bin/env python3
"""
Test script to verify single_case_event_pipeline imports work
"""

def test_imports():
    """Test if all imports work correctly"""
    
    print("🧪 TESTING SINGLE CASE EVENT PIPELINE IMPORTS")
    print("=" * 50)
    
    try:
        print("\n1. Testing process_new_event import...")
        from docketwatch_rss_trigger import process_new_event
        print("   ✅ process_new_event imported successfully")
        
        print("\n2. Testing log_message import...")
        from scraper_base import log_message
        print("   ✅ log_message imported successfully")
        
        print("\n3. Testing single_case_event_pipeline main function...")
        import single_case_event_pipeline
        print("   ✅ single_case_event_pipeline module imported successfully")
        
        print("\n🎉 ALL IMPORTS SUCCESSFUL!")
        print("   The ImportError has been fixed.")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        return False

def show_usage():
    """Show correct usage"""
    
    print("\n📋 CORRECT USAGE:")
    print("=" * 50)
    print("\npython single_case_event_pipeline.py <case_id> <event_no> <court_code>")
    print("\nExamples:")
    print("  python single_case_event_pipeline.py 12345 67 cacd")
    print("  python single_case_event_pipeline.py 98765 123 nysd")

if __name__ == "__main__":
    success = test_imports()
    
    if success:
        show_usage()
        print(f"\n✅ The single case event pipeline is ready to use!")
    else:
        print(f"\n❌ Fix the import errors before using the pipeline.")
