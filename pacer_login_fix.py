"""
PACER Login Fix - Temporary patch for PACER login issues

This script provides a working PACER login function that can be used
by the scraper when the CSS selector-based login fails.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def pacer_login_direct(driver, username, password, cursor=None, fk_task_run=None):
    """
    Direct PACER login using hardcoded element names (like working scripts)
    """
    try:
        # Navigate to PACER login page
        driver.get("https://pacer.login.uscourts.gov/csologin/login.jsf")
        time.sleep(2)
        
        # Fill in username using NAME selector (not CSS)
        username_field = driver.find_element(By.NAME, "loginForm:loginName")
        username_field.clear()
        username_field.send_keys(username)
        
        # Fill in password using NAME selector
        password_field = driver.find_element(By.NAME, "loginForm:password")
        password_field.clear()
        password_field.send_keys(password)
        
        # Fill in client code if field exists
        try:
            client_code_field = driver.find_element(By.NAME, "loginForm:clientCode")
            client_code_field.clear()
            client_code_field.send_keys("DocketWatch")
        except:
            pass  # Client code field might not exist
        
        # Click login button
        login_button = driver.find_element(By.NAME, "loginForm:fbtnLogin")
        login_button.click()
        
        time.sleep(3)
        
        if cursor and fk_task_run:
            from scraper_base import log_message
            log_message(cursor, fk_task_run, "INFO", "PACER direct login successful")
        
        return True
        
    except Exception as e:
        if cursor and fk_task_run:
            from scraper_base import log_message
            log_message(cursor, fk_task_run, "ERROR", f"PACER direct login failed: {e}")
        print(f"PACER login error: {e}")
        return False
