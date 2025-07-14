import time
import os
import requests
import pyodbc
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from twocaptcha import TwoCaptcha  # ✅ Using 2Captcha Python SDK

# Setup Logging
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\captcha_test.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("=== Script Started ===")

# Database Connection
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = pyodbc.connect(DB_CONNECTION)
cursor = conn.cursor()

# Fetch CAPTCHA API Key
def get_captcha_api():
    cursor.execute("SELECT captcha_api FROM [docketwatch].[dbo].[utilities] WHERE id = 1")
    api_key = cursor.fetchone()
    return api_key[0] if api_key else None

API_KEY = get_captcha_api()
if not API_KEY:
    logging.error("No 2Captcha API Key found in database!")
    raise ValueError("No 2Captcha API Key found in database!")

# Setup 2Captcha Solver
solver = TwoCaptcha(API_KEY)

# Setup ChromeDriver
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("--headless=new")  # ✅ Runs in headless mode

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open Case Lookup Page
SITE_URL = "https://caselookup.nmcourts.gov/caselookup/app"
driver.get(SITE_URL)

# Click "I Accept" Button & Extract Cookies
try:
    time.sleep(2)  # Slight delay to appear human-like
    accept_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "Submit"))
    )
    accept_button.click()
    logging.info("Clicked 'I Accept' button.")
    time.sleep(3)

    # Extract Cookies
    cookies = driver.get_cookies()
    session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
    logging.info(f"Extracted Session Cookies: {session_cookies}")

except Exception as e:
    logging.error(f"Could not click 'I Accept' button: {e}")
    driver.quit()
    exit()

# Extract the Correct Sitekey Dynamically
try:
    sitekey_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-sitekey]"))
    )
    SITE_KEY = sitekey_element.get_attribute("data-sitekey")
    logging.info(f"Extracted Sitekey: {SITE_KEY}")
except Exception as e:
    logging.error(f"Error extracting Sitekey: {e}")
    driver.quit()
    exit()

# Solve CAPTCHA Using 2Captcha
logging.info("Sending CAPTCHA to 2Captcha for solving...")
try:
    result = solver.recaptcha(sitekey=SITE_KEY, url=SITE_URL)
    captcha_solution = result['code']
    logging.info(f"CAPTCHA Solved: {captcha_solution}")
except Exception as e:
    logging.error(f"2Captcha Error: {e}")
    driver.quit()
    exit()

# Inject CAPTCHA Solution into Page
try:
    driver.execute_script(f'document.getElementById("g-recaptcha-response").innerText = "{captcha_solution}";')
    logging.info("Injected CAPTCHA solution into page.")

    # Dispatch events to make sure reCAPTCHA registers the token
    for event in ["input", "change", "blur", "keyup", "keydown"]:
        driver.execute_script(f'document.getElementById("g-recaptcha-response").dispatchEvent(new Event("{event}", {{ bubbles: true }}));')

    time.sleep(2)  # Give time for reCAPTCHA to process

    # Click the "Verify" or "Submit" Button if present
    try:
        verify_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "recaptcha-verify-button"))
        )
        verify_button.click()
        logging.info("Clicked reCAPTCHA 'Verify' button.")
        time.sleep(2)
    except:
        logging.info("No 'Verify' button found, proceeding.")

except Exception as e:
    logging.error(f"Error injecting CAPTCHA solution: {e}")
    driver.quit()
    exit()

# Click "Continue" Button After CAPTCHA
try:
    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "Submit"))
    )
    driver.execute_script("arguments[0].scrollIntoView();", submit_button)
    submit_button.click()
    logging.info("Clicked 'Continue to Case Lookup' button.")
    time.sleep(3)
except Exception as e:
    logging.error(f"Error clicking 'Continue to Case Lookup' button: {e}")
    driver.quit()
    exit()

# Confirm We Reached the Case Search Page
try:
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "dl2"))
    )
    logging.info("Successfully reached the case search page!")
except:
    logging.error("Still stuck on CAPTCHA or failed to reach case search page.")
    driver.quit()
    exit()

# 🚀 SEARCHING FOR CASE EVENTS 🚀 #

# Fetch Cases from Database
cursor.execute("SELECT id, case_number, courttype, courtlocation, courtcategory, courtcasenumber FROM docketwatch.dbo.cases WHERE courtcasenumber IS NOT NULL")
cases = cursor.fetchall()

for case in cases:
    case_id, case_number, courttype, courtlocation, courtcategory, courtcasenumber = case

    logging.info(f"Searching for case: {case_number}")

    # Click on "Case Number Search" Tab
    try:
        case_search_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "dl2"))
        )
        case_search_tab.click()
        time.sleep(3)
    except Exception as e:
        logging.error(f"Error clicking 'Case Number Search' tab: {e}")
        continue

    # Enter Case Information
    try:
        driver.find_element(By.ID, "courtType").send_keys(courttype)
        driver.find_element(By.ID, "courtLocation").send_keys(courtlocation)
        driver.find_element(By.ID, "caseCategory").send_keys(courtcategory)
        driver.find_element(By.ID, "caseNumber").send_keys(courtcasenumber)

        # Submit Search
        driver.find_element(By.ID, "Submit").click()
        time.sleep(3)
    except Exception as e:
        logging.error(f"Error entering case details: {e}")
        continue

    # Extract Case Events
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table.details tr")
        for row in rows[1:]:  # Skip header row
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) == 6:
                event_date = cols[0].text.strip()
                event_description = cols[1].text.strip()
                event_result = cols[2].text.strip()
                party_type = cols[3].text.strip()
                party_number = cols[4].text.strip()
                amount = cols[5].text.strip()

                # Insert into case_events table only if the event doesn't already exist
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.case_events (event_date, event_description, event_result, party_type, party_number, amount, fk_cases, created_at)
                    SELECT ?, ?, ?, ?, ?, ?, ?, GETDATE()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM docketwatch.dbo.case_events 
                        WHERE fk_cases = ? 
                        AND event_date = ? 
                        AND event_description = ?
                    )
                """, event_date, event_description, event_result, party_type, party_number, amount, case_id, case_id, event_date, event_description)

                conn.commit()

        
        logging.info(f"Stored case events for {case_number}")

    except Exception as e:
        logging.error(f"Error extracting case events for {case_number}: {e}")
        continue

# Close Browser
driver.quit()
logging.info("Script Completed Successfully!")
