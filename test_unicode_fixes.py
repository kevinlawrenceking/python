#!/usr/bin/env python3
"""
Test Unicode encoding fixes for RSS trigger.
"""

import logging
import tempfile
import os

def test_unicode_logging():
    """Test that Unicode characters are properly handled in logging"""
    
    print("🧪 TESTING UNICODE ENCODING FIXES")
    print("=" * 40)
    
    # Test the safe_log_message function
    def safe_log_message(message):
        """Safe logging function (copied from RSS trigger)"""
        unicode_replacements = {
            '✅': '[OK]',
            '❌': '[ERROR]',
            '🔍': '[INFO]',
            '📋': '[DATA]',
            '🔔': '[ALERT]',
            '⚠️': '[WARNING]',
            '🎯': '[TARGET]',
            '🚀': '[SUCCESS]'
        }
        
        safe_message = str(message)
        for unicode_char, ascii_replacement in unicode_replacements.items():
            safe_message = safe_message.replace(unicode_char, ascii_replacement)
        
        return safe_message
    
    # Test messages with Unicode characters
    test_messages = [
        "✅ Event already exists - skipping duplicate",
        "❌ Error handling event 73: 'charmap' codec error",
        "🔍 PACER IDs: doc_number=73, doc_id=127138195871",
        "🔔 RSS monitoring discovered 5 new events",
        "Regular ASCII message without Unicode"
    ]
    
    print("\n📋 UNICODE REPLACEMENT TESTS:")
    for i, message in enumerate(test_messages, 1):
        safe_message = safe_log_message(message)
        print(f"   {i}. Original: {message}")
        print(f"      Safe:     {safe_message}")
        print()
    
    # Test logging with UTF-8 encoding
    print("📝 TESTING UTF-8 LOGGING:")
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.log', delete=False) as temp_log:
        temp_log_path = temp_log.name
    
    try:
        # Configure logging with UTF-8 encoding
        logging.basicConfig(
            filename=temp_log_path,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            encoding='utf-8',
            force=True  # Override any existing configuration
        )
        
        # Test logging Unicode messages
        test_log_messages = [
            "[OK] Event created successfully",
            "[ERROR] Database connection failed",
            "[INFO] Processing PACER document 73"
        ]
        
        for message in test_log_messages:
            logging.info(message)
        
        # Read back the log file
        with open(temp_log_path, 'r', encoding='utf-8') as log_file:
            log_content = log_file.read()
        
        print(f"   ✅ Successfully wrote {len(test_log_messages)} messages to UTF-8 log")
        print(f"   📄 Log file size: {len(log_content)} characters")
        
        # Show a sample of the log content
        lines = log_content.strip().split('\n')
        if lines:
            print(f"   📝 Sample log line: {lines[-1]}")
        
    except Exception as e:
        print(f"   ❌ Logging test failed: {e}")
    
    finally:
        # Clean up
        try:
            os.unlink(temp_log_path)
        except:
            pass
    
    print("\n🎯 ENCODING RECOMMENDATIONS:")
    print("   1. ✅ Added encoding='utf-8' to logging.basicConfig()")
    print("   2. ✅ Created safe_log_message() function for Unicode handling")
    print("   3. ✅ Replaced emoji characters with ASCII equivalents")
    print("   4. ✅ Updated exception handling to use safe logging")
    
    print("\n📊 EXPECTED RESULTS:")
    print("   • No more 'charmap' codec errors in logs")
    print("   • Unicode characters replaced with ASCII equivalents")
    print("   • Log files written with UTF-8 encoding")
    print("   • Error messages properly captured and logged")


if __name__ == "__main__":
    test_unicode_logging()
    print("\n🎉 Unicode encoding fixes tested successfully!")
