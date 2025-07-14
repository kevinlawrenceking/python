from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time
import random

# PACER login credentials
USERNAME = "TMZFEDPACER"
PASSWORD = "Courtpacer19D!"

# URLs
LOGIN_URL = "https://pacer.login.uscourts.gov/csologin/login.jsf"
CASE_URL = "https://ecf.nysd.uscourts.gov/cgi-bin/iquery.pl?548323889359067-L_9999_1-0-635145"

# Set up Selenium WebDriver
driver = webdriver.Chrome()

def human_pause(min_time=1, max_time=3):
    """Randomized pauses to mimic human behavior."""
    time.sleep(random.uniform(min_time, max_time))

try:
    # Open PACER login page
    driver.get(LOGIN_URL)
    print("Loading PACER login page...")
    human_pause(2, 4)

    # Locate username and password fields
    username_input = driver.find_element(By.NAME, "loginForm:loginName")
    password_input = driver.find_element(By.NAME, "loginForm:password")

    # Enter credentials with human-like pauses
    print("Entering username...")
    username_input.send_keys(USERNAME)
    human_pause(1, 2)

    print("Entering password...")
    password_input.send_keys(PASSWORD)
    human_pause(2, 3)

    # Locate and click the login button
    print("Clicking login button...")
    login_button = driver.find_element(By.NAME, "loginForm:fbtnLogin")
    login_button.click()
    human_pause(3, 5)

    # Navigate to case page
    print("Assuming login success. Redirecting to case page...")
    driver.get(CASE_URL)
    human_pause(3, 5)
    print("Case page loaded:", driver.current_url)

    # Locate and click the "Docket Report" link
    print("Clicking 'Docket Report' link...")
    docket_link = driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report")
    docket_link.click()
    human_pause(3, 5)

    # Uncheck "Parties and Counsel"
    print("Unchecking 'Parties and Counsel'...")
    parties_counsel_checkbox = driver.find_element(By.NAME, "list_of_parties_and_counsel")
    if parties_counsel_checkbox.is_selected():
        parties_counsel_checkbox.click()
    human_pause(1, 2)

    # Uncheck "Terminated Parties"
    print("Unchecking 'Terminated Parties'...")
    terminated_parties_checkbox = driver.find_element(By.NAME, "terminated_parties")
    if terminated_parties_checkbox.is_selected():
        terminated_parties_checkbox.click()
    human_pause(1, 2)

    # Select "Most recent date first"
    print("Sorting by most recent date first...")
    sort_dropdown = Select(driver.find_element(By.NAME, "sort1"))
    sort_dropdown.select_by_visible_text("Most recent date first")
    human_pause(1, 2)

    # Click "Run Report" button
    print("Running docket report...")
    run_report_button = driver.find_element(By.NAME, "button1")
    run_report_button.click()
    human_pause(3, 5)

    print("Docket report has been generated.")

except Exception as e:
    print(f"Error: {e}")

finally:
    # Keep browser open for debugging
    input("Press Enter to close the browser...")
    driver.quit()
