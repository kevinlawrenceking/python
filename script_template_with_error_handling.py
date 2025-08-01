"""
Template for DocketWatch Scripts with Chrome Cleanup and Error Notifications

This template provides the essential structure that ALL DocketWatch scripts should follow:
1. Proper Chrome driver cleanup with try/finally
2. Comprehensive error notification via email
3. Database error logging
4. Graceful error handling

INSTRUCTIONS FOR EACH SCRIPT:
1. Copy this template structure
2. Replace [SCRIPT_LOGIC_HERE] with your specific script logic
3. Add specific error handling for your script's operations
4. Test the script to ensure errors trigger email notifications

REQUIREMENTS:
- error_notification_system.py must be in the same directory
- Database table 'error_notifications' must exist (run create_error_notifications_table.sql)
- SMTP configuration must be set up in the database utilities table
"""

import os
import sys
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from error_notification_system import create_error_notifier

# Setup Error Notification System
script_name = os.path.splitext(os.path.basename(__file__))[0]
error_notifier = create_error_notifier(script_name)

# === ESSENTIAL CHROME CLEANUP PATTERN ===
driver = None
try:
    # === CHROME DRIVER SETUP ===
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless=new")  # Use new headless mode
    
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # === YOUR SCRIPT LOGIC GOES HERE ===
    # Replace this section with your specific script logic:
    
    # [SCRIPT_LOGIC_HERE]
    
    # Example of how to handle specific errors in your script:
    try:
        # Your specific operations (login, scraping, etc.)
        driver.get("https://example.com")
        # ... more operations ...
        
    except Exception as e:
        # Log specific error types with appropriate categories
        error_notifier.log_chrome_error(f"Failed to load page: {str(e)}")
        raise  # Re-raise to be caught by outer handler
    
    print("Script completed successfully!")
    
finally:
    # === ESSENTIAL: ALWAYS CLEAN UP CHROME DRIVER ===
    if driver:
        try:
            driver.quit()
            print("ChromeDriver properly closed.")
        except Exception as cleanup_error:
            error_msg = f"Error during driver cleanup: {str(cleanup_error)}"
            print(error_msg)
            error_notifier.log_chrome_error(error_msg)

except Exception as e:
    # === ESSENTIAL: TOP-LEVEL ERROR HANDLING ===
    error_msg = f"Critical script failure: {str(e)}"
    print(error_msg)
    
    # Log critical error with full context
    error_notifier.log_critical_error(
        error_msg,
        additional_context=f"Stack trace: {traceback.format_exc()}"
    )
    
    # Re-raise the exception so the script still fails properly
    raise

# === END OF TEMPLATE ===

"""
CHECKLIST FOR EACH SCRIPT:

✅ Chrome Cleanup:
   - driver = None before try block
   - driver.quit() in finally block
   - Error handling around driver.quit()

✅ Error Notifications:
   - Import error_notification_system
   - Create error_notifier at script start
   - Use appropriate error logging methods:
     * error_notifier.log_chrome_error() for Selenium issues
     * error_notifier.log_database_error() for DB issues
     * error_notifier.log_authentication_error() for login issues
     * error_notifier.log_critical_error() for major failures
     * error_notifier.log_pdf_error() for PDF processing issues

✅ Top-level Exception Handler:
   - Catch all unhandled exceptions
   - Log as critical error with notification
   - Re-raise exception to maintain proper exit codes

✅ Testing:
   - Test that Chrome closes properly on both success and failure
   - Test that error emails are sent for different error types
   - Verify error logging in database
"""

"""
COMMON SCRIPTS THAT NEED THIS PATTERN:

1. Scripts using Selenium/Chrome:
   - docketwatch_case_events.py ✅ (DONE)
   - docketwatch_map_scraper.py ✅ (DONE)
   - docketwatch_map_unfiled_scraper.py (Partial - needs error notifications)
   - docketwatch_broward_scraper.py
   - docketwatch_la_scraper.py
   - docketwatch_nyc_scraper.py
   - docketwatch_nycsc_scraper.py
   - Any other *_scraper.py files

2. Scripts with critical operations:
   - batch_case_summarizer.py
   - pacer_case_event_pdf_summarizer.py
   - map_case_summarizer.py
   - supreme_court_monitor.py ✅ (Partial - has logging)

3. Scripts that process data:
   - case_processing.py
   - batch_generate_map_summaries.py
   - extract_pacer_pdf_metadata_loop.py
"""
