import pyodbc
import time
import json
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === Logging setup ===
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\map_update.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def log(msg):
    print(msg)
    logging.info(msg)

# === Constants ===
TOOL_ID = 6
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

# === DB connection with autocommit ===
log("Connecting to database with autocommit...")
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;", autocommit=True)
cursor = conn.cursor()

# === Fetch login info for MAP ===
log("Fetching login credentials from tools table...")
cursor.execute("""
    SELECT [login_url], [username], [pass], [search_url]
    FROM [docketwatch].[dbo].[tools]
    WHERE id = ?
""", (TOOL_ID,))
login_url, username, password, _ = cursor.fetchone()
log("Credentials and URL fetched.")

# === Launch browser and login ===
log("Launching headless Chrome browser...")
options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

try:
    log("Navigating to login page...")
    driver.get(login_url)
    wait = WebDriverWait(driver, 20)

    log("Filling out login form...")
    wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
    wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()

    log("Waiting for post-login redirect...")
    time.sleep(5)
    current_url = driver.current_url

    if "signin-oidc" in current_url or "media.lacourt.org" in current_url:
        log("✅ Login successful.")
    else:
        log(f"❌ Login may have failed. Current URL: {current_url}")
        driver.quit()
        exit()

except Exception as e:
    log(f"❌ Login failed: {e}")
    driver.quit()
    exit()

# === Transfer cookies to Requests session ===
log("Transferring session cookies to Requests...")
session = requests.Session()
for cookie in driver.get_cookies():
    session.cookies.set(cookie["name"], cookie["value"])
driver.quit()

# === Query all missing map_id cases ===
log("Querying cases with missing map_id...")
cursor.execute("""
    SELECT c.id, c.case_number
    FROM docketwatch.dbo.cases c
    WHERE c.fk_tool IN (6, 12)
      AND c.map_id IS NULL
      AND c.status = 'Tracked'
""")
rows = cursor.fetchall()
log(f"Found {len(rows)} cases to update.")

# === Loop through cases ===
for row_id, case_number in rows:
    try:
        log(f"Processing case {case_number} (tool_case_id = {row_id})...")
        url = f"https://media.lacourt.org/api/AzureApi/GetCaseList/{case_number}"
        resp = session.get(url)
        data = resp.json()

        if data.get("IsSuccess") and data.get("ResultList"):
            non_criminal = data["ResultList"][0].get("NonCriminalCases", [])
            if non_criminal:
                map_id = non_criminal[0].get("CaseID")
                if map_id:
                    # Build and log fully resolved SQL
                    update_sql_printable = f"""
UPDATE docketwatch.dbo.cases
SET map_id = '{map_id}'
WHERE id = {row_id}
""".strip()
                    log(f"SQL EXECUTING:\n{update_sql_printable}")
                    
                    cursor.execute("UPDATE docketwatch.dbo.cases SET map_id = ? WHERE id = ?", (map_id, row_id))
                    log(f"✅ Updated {case_number} → map_id = {map_id}")
                else:
                    log(f"⚠️ Skipping {case_number}: CaseID is empty or null")
            else:
                log(f"⚠️ No NonCriminalCases found for {case_number}")
        else:
            log(f"⚠️ API response invalid or empty for {case_number}: {json.dumps(data)}")

    except Exception as e:
        log(f"❌ Error processing {case_number}: {e}")

# === Finalize ===
cursor.close()
conn.close()
log("✅ Script complete. Database connection closed.")
