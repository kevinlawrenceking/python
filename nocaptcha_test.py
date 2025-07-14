import time
import requests
import pyodbc
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ✅ Setup Logging
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\captcha_test.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("=== Script Started ===")

# ✅ Database Connection
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = pyodbc.connect(DB_CONNECTION)
cursor = conn.cursor()

# ✅ Setup ChromeDriver
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# ✅ Open Case Lookup Page
SITE_URL = "https://caselookup.nmcourts.gov/caselookup/app"
driver.get(SITE_URL)

# ✅ Inject Session Cookies (Captured from Manual Login)
session_cookies = {
    "JSESSIONID": "FB8BA56A4B49A153CAE9F0A010144AD7",  # Replace with extracted value
    "_ga": "GA1.1.504301106.1741981308",  
    "_ga_FK4K3XGHQG": "GS1.1.1741981307.1.0.1741981317.0.0.0"
}

for cookie_name, cookie_value in session_cookies.items():
    driver.add_cookie({"name": cookie_name, "value": cookie_value, "domain": "caselookup.nmcourts.gov"})

# ✅ Reload Page to Apply Cookies
driver.get(SITE_URL)
logging.info("✅ Session cookies applied. Reloading page...")

# ✅ Check If CAPTCHA Page Is Skipped
try:
    # Look for an element that exists *after* CAPTCHA (indicating we bypassed it)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "dl2"))  # ID of the "Case Number Search" tab
    )
    logging.info("✅ CAPTCHA skipped using session cookies!")
except Exception as e:
    logging.error(f"❌ Still on CAPTCHA page. Error: {e}")
    driver.quit()
    exit()

# ✅ Click "I Accept" Button (if required)
try:
    accept_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.ID, "Submit"))
    )
    accept_button.click()
    logging.info("✅ Clicked 'I Accept' button.")
    time.sleep(3)
except Exception:
    logging.info("✅ No 'I Accept' button needed. Proceeding...")

# ✅ Close Database and Browser
cursor.close()
conn.close()
driver.quit()
logging.info("🎯 Script Completed Successfully!")
