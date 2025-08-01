"""
DocketWatch Error Notification System
Provides centralized error logging and email notification for critical errors.
"""

import os
import sys
import smtplib
import traceback
import pyodbc
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import logging

class ErrorNotificationSystem:
    """
    Centralized error notification system for DocketWatch scripts.
    
    Features:
    - Logs errors to database
    - Sends email notifications for critical errors
    - Prevents duplicate notifications
    - Tracks error resolution
    """
    
    def __init__(self, script_name: str, db_connection_string: str = None):
        self.script_name = script_name
        self.db_connection_string = db_connection_string or "DSN=Docketwatch;TrustServerCertificate=yes;"
        self.notification_email = "kevin@tmz.com"  # Primary notification email
        self.smtp_config = self._get_smtp_config()
        
    def _get_smtp_config(self) -> Dict[str, Any]:
        """Get SMTP configuration - use same settings as scraper_base.py"""
        # Use the same SMTP configuration as scraper_base.py
        return {
            'server': 'mx0a-00195501.pphosted.com',
            'port': 25,
            'username': '',  # No authentication needed for this SMTP server
            'password': '',
            'use_tls': False  # Port 25 typically doesn't use TLS
        }
    
    def log_error(self, 
                  error_type: str, 
                  error_message: str, 
                  severity: str = "ERROR",
                  fk_task_run: Optional[int] = None,
                  fk_case: Optional[int] = None,
                  additional_context: Optional[str] = None,
                  send_email: bool = True) -> int:
        """
        Log an error to the database and optionally send email notification.
        
        Args:
            error_type: Type/category of error (e.g., "Database Connection", "Chrome Driver")
            error_message: Detailed error message
            severity: ERROR, CRITICAL, WARNING
            fk_task_run: Optional task run ID
            fk_case: Optional case ID
            additional_context: Additional context information
            send_email: Whether to send email notification
            
        Returns:
            int: Error notification ID
        """
        try:
            # Get stack trace
            stack_trace = traceback.format_exc() if sys.exc_info()[0] is not None else None
            
            # Insert into database
            conn = pyodbc.connect(self.db_connection_string)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO dbo.error_notifications (
                    script_name, error_type, error_message, severity, 
                    stack_trace, fk_task_run, fk_case, additional_context
                )
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.script_name, error_type, error_message, severity,
                  stack_trace, fk_task_run, fk_case, additional_context))
            
            error_id = cursor.fetchone()[0]
            conn.commit()
            
            # Send email notification if requested and severity warrants it
            if send_email and severity in ['ERROR', 'CRITICAL']:
                self._send_email_notification(error_id, error_type, error_message, severity, stack_trace)
                
                # Mark email as sent
                cursor.execute("""
                    UPDATE dbo.error_notifications 
                    SET email_sent = 1, email_sent_timestamp = GETDATE()
                    WHERE id = ?
                """, (error_id,))
                conn.commit()
            
            cursor.close()
            conn.close()
            
            return error_id
            
        except Exception as e:
            # Fallback logging if database fails
            print(f"CRITICAL: Failed to log error to database: {e}")
            print(f"Original error - {error_type}: {error_message}")
            return -1
    
    def _send_email_notification(self, error_id: int, error_type: str, error_message: str, severity: str, stack_trace: str = None):
        """Send email notification for the error."""
        try:
            # No authentication needed for our SMTP server (same as scraper_base.py)
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = 'it@tmz.com'  # Use same From address as scraper_base.py
            msg['To'] = self.notification_email
            msg['Subject'] = f"DocketWatch {severity}: {self.script_name} - {error_type}"
            
            # Email body
            body = f"""
DocketWatch Error Notification

Script: {self.script_name}
Error ID: {error_id}
Severity: {severity}
Error Type: {error_type}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Error Message:
{error_message}

Stack Trace:
{stack_trace or 'No stack trace available'}

Server: {os.getenv('COMPUTERNAME', 'Unknown')}
Environment: Production

Please investigate this error promptly.

---
DocketWatch Automated Error Notification System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email using same method as scraper_base.py
            with smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port']) as server:
                # No authentication needed for this SMTP server
                server.sendmail('it@tmz.com', self.notification_email, msg.as_string())
            
            print(f"Error notification email sent for error ID {error_id}")
            return True
            
        except Exception as e:
            print(f"Failed to send error notification email: {e}")
            return False
    
    def log_critical_error(self, error_message: str, **kwargs):
        """Log a critical error that requires immediate attention."""
        return self.log_error("Critical Error", error_message, severity="CRITICAL", **kwargs)
    
    def log_chrome_error(self, error_message: str, **kwargs):
        """Log a Chrome/Selenium related error."""
        return self.log_error("Chrome Driver Error", error_message, severity="ERROR", **kwargs)
    
    def log_database_error(self, error_message: str, **kwargs):
        """Log a database related error."""
        return self.log_error("Database Error", error_message, severity="ERROR", **kwargs)
    
    def log_authentication_error(self, error_message: str, **kwargs):
        """Log an authentication related error."""
        return self.log_error("Authentication Error", error_message, severity="ERROR", **kwargs)
    
    def log_pdf_error(self, error_message: str, **kwargs):
        """Log a PDF processing related error."""
        return self.log_error("PDF Processing Error", error_message, severity="ERROR", **kwargs)
    
    def mark_resolved(self, error_id: int, resolved_by: str = "System"):
        """Mark an error as resolved."""
        try:
            conn = pyodbc.connect(self.db_connection_string)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE dbo.error_notifications 
                SET resolved = 1, resolved_timestamp = GETDATE(), resolved_by = ?
                WHERE id = ?
            """, (resolved_by, error_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Failed to mark error {error_id} as resolved: {e}")
            return False

# Convenience function for easy import
def create_error_notifier(script_name: str) -> ErrorNotificationSystem:
    """Create an error notifier for the given script."""
    return ErrorNotificationSystem(script_name)

# Global exception handler decorator
def with_error_notification(script_name: str):
    """Decorator to automatically handle and notify about unhandled exceptions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            notifier = create_error_notifier(script_name)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                notifier.log_critical_error(
                    f"Unhandled exception in {func.__name__}: {str(e)}",
                    additional_context=f"Function: {func.__name__}, Args: {args}, Kwargs: {kwargs}"
                )
                raise
        return wrapper
    return decorator

if __name__ == "__main__":
    # Test the error notification system
    notifier = create_error_notifier("test_script.py")
    
    # Test different types of errors
    notifier.log_error("Test Error", "This is a test error message", severity="WARNING", send_email=False)
    notifier.log_chrome_error("Chrome failed to start", send_email=False)
    notifier.log_database_error("Connection timeout", send_email=False)
    
    print("Error notification system test completed")
