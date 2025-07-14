import os
import sys
import time
import json
import pyodbc
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === Get date param from command line ===
if len(sys.argv) < 2:
    print("Usage: python test_recent_filings.py MM-DD-YYYY")
    sys.exit(1)

input_date = sys.argv[1]
try:
    dt = datetime.strptime(input_date, "%m-%d-%Y")
    date_for_url = dt.strftime("%m-%d-%Y")
    date_for_file = dt.strftime("%m%d%Y")
except ValueError:
    print("Invalid date format. Use MM-DD-YYYY.")
    sys.exit(1)

# === DB: Fetch login credentials (tool id = 6) ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()
cursor.execute("""
    SELECT [login_url], [username], [pass]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = 6
""")
row = cursor.fetchone()
login_url, username, password = row

# === Setup ChromeDriver ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# === Step 1: Log into media.lacourt.org ===
try:
    print(f"Navigating to: {login_url}")
    driver.get(login_url)
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()

    time.sleep(5)
    if "signin-oidc" in driver.current_url or "media.lacourt.org" in driver.current_url:
        print("Login successful.")
    else:
        print(f"Login failed. Current URL: {driver.current_url}")
        driver.quit()
        sys.exit(1)

    cookies = driver.get_cookies()
    cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
    driver.quit()
except Exception as e:
    print(f"Login failed: {e}")
    driver.quit()
    sys.exit(1)

# === Step 2: Call GetRecentFilings for provided date ===
api_url = f"https://media.lacourt.org/api/AzureApi/GetRecentFilings/{date_for_url}/{date_for_url}"
headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}

print(f"Requesting: {api_url}")
response = requests.get(api_url, headers=headers)

# === Step 3: Parse + Save JSON ===
try:
    data = response.json()
    log_path = rf"\\10.146.176.84\general\docketwatch\python\logs\recent_filings_{date_for_file}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"JSON saved to: {log_path}")
    print(json.dumps(data, indent=2))

except Exception as e:
    print(f"Failed to parse or save JSON: {e}")
