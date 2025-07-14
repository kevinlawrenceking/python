import requests
import pyodbc
import time
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === SETTINGS ===
TOOL_ID = 6
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
SAVE_DIR = Path(r"\\10.146.176.84\general\docketwatch\map_test_pdf")
TARGET_DATE = datetime.now().strftime("%m-%d-%Y")  # Use today

# === Get login credentials from DB ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()
cursor.execute("""
    SELECT [login_url], [username], [pass]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = ?
""", (TOOL_ID,))
row = cursor.fetchone()
login_url, username, password = row

# === Login via Selenium ===
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# chrome_options.add_argument("--headless=new")  # Optional
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print(f"[+] Logging in at {login_url}")
    driver.get(login_url)
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()

    time.sleep(5)
    cookies = driver.get_cookies()
    cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
    print("[+] Login successful.")
finally:
    driver.quit()

# === Step 1: Get Recent Filings for today ===
headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}
api_url = f"https://media.lacourt.org/api/AzureApi/GetRecentFilings/{TARGET_DATE}/{TARGET_DATE}"
print(f"[+] Requesting filings: {api_url}")
response = requests.get(api_url, headers=headers)
filings = response.json().get("ResultList", [])

if not filings:
    print("[-] No filings found for today.")
    exit()

first_filing = filings[0]
lead_doc_id = first_filing["LeadDocument"]["LeadDocumentID"]
print(f"[+] Found filing: {lead_doc_id}")

# === Step 2: ViewEcourtDocument call ===
view_url = f"https://media.lacourt.org/api/AzureApi/ViewEcourtDocument/{lead_doc_id}"
print(f"[+] Triggering PDF creation: {view_url}")
trigger_response = requests.get(view_url, headers=headers)

if trigger_response.status_code != 200:
    print(f"[-] Failed to call ViewEcourtDocument: {trigger_response.status_code}")
    exit()

result = trigger_response.json().get("ResultList", [])[0]
filename = next((item["Value"] for item in result["OtherInformation"] if item["Key"] == "FileName"), None)
file_location = result.get("FileLocation", "")
folder = file_location.split("\\")[-2] if file_location else datetime.now().strftime("%Y%m%d")

if not filename:
    print("[-] No FileName found in result.")
    exit()

filename += ".pdf"
pdf_url = f"https://media.lacourt.org/api/Documents/pdfs/{folder}/{filename}"
print(f"[+] Constructed PDF URL: {pdf_url}")

# === Step 3: Try to download PDF ===
SAVE_DIR.mkdir(parents=True, exist_ok=True)
pdf_path = SAVE_DIR / filename

for attempt in range(1, 4):
    print(f"[+] Attempt {attempt}: Downloading {pdf_url}")
    pdf_response = requests.get(pdf_url, headers=headers)
    if pdf_response.status_code == 200:
        with open(pdf_path, "wb") as f:
            f.write(pdf_response.content)
        print(f"[✓] PDF saved to {pdf_path}")
        break
    elif pdf_response.status_code == 404:
        print("[-] PDF not yet ready (404). Retrying...")
        time.sleep(3)
    else:
        print(f"[-] Unexpected response: {pdf_response.status_code}")
        break
else:
    print(f"[✗] Failed to retrieve PDF after retries.")

# === Cleanup ===
cursor.close()
conn.close()
