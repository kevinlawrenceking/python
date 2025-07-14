
import os
import subprocess
import time
import json
import pyodbc
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === CONFIG ===
LEAD_DOCUMENT_ID = "750591547"  # Example; replace dynamically if needed
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
TOOL_ID = 6

# === Step 1: DB Login Info ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()
cursor.execute("""
    SELECT [login_url], [username], [pass]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = ?
""", (TOOL_ID,))
row = cursor.fetchone()
login_url, username, password = row

# === Step 2: Login with Selenium ===
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

print("[+] Logging in via browser...")
driver.get(login_url)
wait = WebDriverWait(driver, 20)
wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()
time.sleep(5)
cookies = driver.get_cookies()
driver.quit()

cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
auth_cookie = cookie_dict.get(".AspNetCore.Cookies")

# === Step 3: ViewEcourtDocument API ===
headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}
view_url = f"https://media.lacourt.org/api/AzureApi/ViewEcourtDocument/{LEAD_DOCUMENT_ID}"
response = requests.get(view_url, headers=headers)
view_data = response.json().get("ResultList", [])[0]

filename = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'FileName'), None)
key = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'ApiKey'), None)
end = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'EndtimeTicks'), None)

# === Step 4: Launch Puppeteer with all vars ===
print("[+] Launching Puppeteer...")
env = {
    "FILE_NAME": filename,
    "KEY": key,
    "END": end,
    "COOKIE": auth_cookie
}

subprocess.run(
   ["node", "\\\\10.146.176.84\\general\\docketwatch\\python\\download_map_filing.js"],
    env={**env, **dict(os.environ), "COURT_CASE_NUMBER": f"{filename}"}
)

