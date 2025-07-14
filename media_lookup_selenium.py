import os
import json
import pyodbc
import time
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === DATABASE CONNECTION & TASK RUN ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# === FETCH CREDENTIALS FROM `tools` (id = 6) ===

# === Fetch credentials and URLs from DB (tool id = 6) ===
cursor.execute("""
    SELECT [login_url], [username], [pass], [search_url]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = 6
""")
login_url, username, password, _ = cursor.fetchone()

chrome_options = Options()
chrome_options.add_argument("--headless=new")   # comment this out for visual debugging
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)

# === SELENIUM LOGIN ===
print("[*] Navigating to login page...")
driver.get(login_url)

wait = WebDriverWait(driver, 20)
print("[*] Waiting for login form to appear...")

wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()

print("[*] Login submitted, waiting for OpenID redirect...")
time.sleep(5)



# Verify login
if "signin-oidc" in driver.current_url or "media.lacourt.org" in driver.current_url:
    print("✅ Login success via browser!")
else:
    print("❌ Login may have failed. Current URL:", driver.current_url)
    driver.quit()
    exit()

# ----------------------------------------
# STEP 2: Extract Cookies and Inject into requests
# ----------------------------------------



session = requests.Session()
for cookie in driver.get_cookies():
    session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

driver.quit()

# ----------------------------------------
# STEP 3: Hit the Case Lookup API
# ----------------------------------------

case_number = '25SMCV01570'
case_url = f'https://media.lacourt.org/api/AzureApi/GetCaseList/{case_number}'

print(f"[*] Looking up case {case_number} via API...")
resp = session.get(case_url)

if resp.ok:
    try:
        data = resp.json()
        if data.get("IsSuccess") and data["ResultList"]:
            case = data["ResultList"][0]["NonCriminalCases"][0]
            print(f"✅ Case found: {case['CaseTitle']} (Judge: {case['JudicialOfficer']})")
        else:
            print("⚠️ Case not found or result list is empty.")
    except Exception as e:
        print("❌ Failed to parse response:", e)
        print(resp.text[:1000])
else:
    print("❌ API request failed. Status:", resp.status_code)
