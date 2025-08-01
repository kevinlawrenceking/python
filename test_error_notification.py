#!/usr/bin/env python3
"""
Quick test script for the error notification system
"""

from error_notification_system import create_error_notifier

def test_error_notification():
    """Test the error notification system"""
    try:
        print("Creating error notifier...")
        error_notifier = create_error_notifier("test_script")
        
        print("Testing database error logging...")
        error_notifier.log_database_error(
            "Test database error - this is a test message",
            fk_task_run=None,
            send_email=False  # Don't actually send email for test
        )
        
        print("Testing critical error logging...")
        error_notifier.log_critical_error(
            "Test critical error - this is a test message",
            fk_task_run=None,
            send_email=False  # Don't actually send email for test
        )
        
        print("✅ Error notification system test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error notification system test failed: {e}")
        return False

if __name__ == "__main__":
    test_error_notification()
