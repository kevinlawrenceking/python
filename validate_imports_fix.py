#!/usr/bin/env python3
"""
Quick import validation for single case pipeline
"""

print("🔍 VALIDATING IMPORTS...")

try:
    # Test the specific imports that were failing
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    print("✅ Basic imports OK")
    
    from docketwatch_rss_trigger import process_new_event
    print("✅ process_new_event imported successfully")
    
    # Test if we can call the function signature
    import inspect
    sig = inspect.signature(process_new_event)
    print(f"✅ Function signature: process_new_event{sig}")
    
    print("\n🎉 IMPORT FIX SUCCESSFUL!")
    print("   The single_case_event_pipeline.py script should now work.")
    print("\n📋 Usage:")
    print("   python single_case_event_pipeline.py <case_id> <event_no> <court_code>")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
