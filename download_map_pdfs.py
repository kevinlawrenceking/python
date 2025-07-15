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

# === Step 2: Find MAP cases needing download ===
cursor.execute("""
    SELECT [id], [courtCaseNumber]
    FROM [docketwatch].[dbo].[cases]
    WHERE id NOT IN (SELECT fk_case FROM docketwatch.dbo.documents)
      AND courtCaseNumber IS NOT NULL
      AND fk_tool = 26
      AND status <> 'Removed'
""")
cases = cursor.fetchall()

if not cases:
    print("No pending cases found.")
    exit(0)

# === Step 3: Login once via Selenium to get cookie ===
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
###chrome_options.add_argument("--headless=new")
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
if not auth_cookie:
    print("Failed to retrieve authentication cookie. Exiting.")
    exit(1)

headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}

# === Step 4: Process each case ===
for case in cases:
    case_id, lead_document_id = case
    print(f"[+] Processing case {case_id} / courtCaseNumber {lead_document_id}...")
    try:
        view_url = f"https://media.lacourt.org/api/AzureApi/ViewEcourtDocument/{lead_document_id}"
        response = requests.get(view_url, headers=headers)
        view_data = response.json().get("ResultList", [])[0]

        filename = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'FileName'), None)
        key = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'ApiKey'), None)
        end = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'EndtimeTicks'), None)

        if not (filename and key and end):
            print(f"  [!] Missing file data for case {case_id}. Skipping.")
            continue

        print(f"[+] Launching Puppeteer/Node for download... File: {filename}")
        env = {
            "FILE_NAME": filename,
            "KEY": key,
            "END": end,
            "COOKIE": auth_cookie,
            "COURT_CASE_NUMBER": str(case_id),
        }
        
        # Capture subprocess output for debugging
        result = subprocess.run(
           ["node", "\\\\10.146.176.84\\general\\docketwatch\\python\\download_map_filing.js"],
            env={**env, **dict(os.environ)},
            capture_output=True,
            text=True
        )
        
        # Check subprocess result
        if result.returncode != 0:
            print(f"  [!] Node.js script failed with return code {result.returncode}")
            print(f"  [!] STDOUT: {result.stdout}")
            print(f"  [!] STDERR: {result.stderr}")
        else:
            print(f"  [+] Node.js script completed successfully")
            if result.stdout:
                print(f"  [+] STDOUT: {result.stdout}")
        
        # Check if PDF was actually downloaded (adjust path as needed)
        expected_pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}\\{filename}"
        if os.path.exists(expected_pdf_path):
            print(f"  [+] PDF successfully saved: {expected_pdf_path}")
        else:
            print(f"  [!] PDF not found at expected location: {expected_pdf_path}")
        
        print(f"  [*] Finished {case_id} / {lead_document_id}")

    except Exception as ex:
        print(f"  [!] Exception for case {case_id}: {ex}")

print("All pending MAP cases processed.")
