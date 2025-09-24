#!/usr/bin/env python3
"""
Test script to demonstrate the debug mode functionality.
"""
import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_debug_mode():
    """Test the debug mode functionality."""
    
    print("🧪 Testing Debug Mode Functionality\n")
    
    # Test 1: Default mode (should be production)
    print("📋 Test 1: Default Mode")
    os.environ.pop('DOCKETWATCH_DEBUG', None)  # Remove env var if it exists
    
    # Need to reimport to get fresh environment variable reading
    if 'docketwatch_case_events_alert_plus2' in sys.modules:
        del sys.modules['docketwatch_case_events_alert_plus2']
    
    from docketwatch_case_events_alert_plus2 import DEBUG_MODE, EMAIL_RECIPIENTS, DEBUG_RECIPIENTS
    
    print(f"   DEBUG_MODE: {DEBUG_MODE}")
    print(f"   Recipients: {EMAIL_RECIPIENTS}")
    print(f"   Expected: Production mode with all recipients\n")
    
    # Test 2: Debug mode enabled
    print("📋 Test 2: Debug Mode Enabled")
    os.environ['DOCKETWATCH_DEBUG'] = 'Y'
    
    # Reimport to get fresh environment variable reading
    if 'docketwatch_case_events_alert_plus2' in sys.modules:
        del sys.modules['docketwatch_case_events_alert_plus2']
    
    from docketwatch_case_events_alert_plus2 import DEBUG_MODE, EMAIL_RECIPIENTS, DEBUG_RECIPIENTS
    
    print(f"   DEBUG_MODE: {DEBUG_MODE}")
    print(f"   Production Recipients: {EMAIL_RECIPIENTS}")
    print(f"   Debug Recipients: {DEBUG_RECIPIENTS}")
    print(f"   Expected: Debug mode with only Kevin's email\n")
    
    # Test 3: Debug mode with lowercase 'y'
    print("📋 Test 3: Debug Mode with lowercase 'y'")
    os.environ['DOCKETWATCH_DEBUG'] = 'y'
    
    # Reimport to get fresh environment variable reading
    if 'docketwatch_case_events_alert_plus2' in sys.modules:
        del sys.modules['docketwatch_case_events_alert_plus2']
    
    from docketwatch_case_events_alert_plus2 import DEBUG_MODE, EMAIL_RECIPIENTS, DEBUG_RECIPIENTS
    
    print(f"   DEBUG_MODE: {DEBUG_MODE}")
    print(f"   Expected: Should be 'Y' (uppercase) due to .upper() call\n")
    
    # Test 4: Debug mode disabled
    print("📋 Test 4: Debug Mode Explicitly Disabled")
    os.environ['DOCKETWATCH_DEBUG'] = 'N'
    
    # Reimport to get fresh environment variable reading
    if 'docketwatch_case_events_alert_plus2' in sys.modules:
        del sys.modules['docketwatch_case_events_alert_plus2']
    
    from docketwatch_case_events_alert_plus2 import DEBUG_MODE, EMAIL_RECIPIENTS, DEBUG_RECIPIENTS
    
    print(f"   DEBUG_MODE: {DEBUG_MODE}")
    print(f"   Expected: Should be 'N' (production mode)\n")
    
    print("✅ Debug mode functionality tests completed!")
    print("\n📝 Usage Instructions:")
    print("   To enable debug mode (Kevin only):")
    print("     Windows: set DOCKETWATCH_DEBUG=Y")
    print("     Linux/Mac: export DOCKETWATCH_DEBUG=Y")
    print("   To disable debug mode:")
    print("     Windows: set DOCKETWATCH_DEBUG=N")
    print("     Linux/Mac: export DOCKETWATCH_DEBUG=N")
    print("   Or simply don't set the environment variable (defaults to production)")
    
    print("\n🔧 Debug Mode Features:")
    print("   • Emails sent only to Kevin.King@tmz.com")
    print("   • Email subject prefixed with [DEBUG]")
    print("   • Debug status logged at startup")
    print("   • Debug recipient list logged when sending")

if __name__ == "__main__":
    test_debug_mode()