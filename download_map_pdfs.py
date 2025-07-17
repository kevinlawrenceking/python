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

# Import from scraper_base
from scraper_base import insert_documents_for_event

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
    WHERE id NOT IN (SELECT fk_case FROM docketwatch.dbo.documents WHERE fk_case IS NOT NULL)
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
if not auth_cookie:
    print("Failed to retrieve authentication cookie. Exiting.")
    exit(1)

headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}

# === Step 4: Process each case ===
for case in cases:
    case_id, court_case_number = case
    print(f"[+] Processing case {case_id} / courtCaseNumber {court_case_number}...")
    try:
        # Check if this is an unfiled case (no courtCaseNumber)
        if court_case_number is None:
            print(f"  [!] Unfiled case with no courtCaseNumber. Skipping case {case_id}.")
            continue
        else:
            # Check if this looks like an unfiled case (no API data available)
            try:
                # Filed case - get document info from API
                view_url = f"https://media.lacourt.org/api/AzureApi/ViewEcourtDocument/{court_case_number}"
                response = requests.get(view_url, headers=headers)
                view_data = response.json().get("ResultList", [])[0]

                filename = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'FileName'), None)
                key = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'ApiKey'), None)
                end = next((x['Value'] for x in view_data['OtherInformation'] if x['Key'] == 'EndtimeTicks'), None)

                if not (filename and key and end):
                    # Treat as unfiled case
                    filename_for_url = f"E{court_case_number}"  # No extension for URL
                    filename_for_file = f"E{court_case_number}.pdf"  # With extension for file
                    print(f"[+] Unfiled case detected. Generated filename: {filename_for_file}")
                    key = ""
                    end = ""
                else:
                    # Filed case - use API filename as-is for URL, ensure .pdf for file
                    filename_for_url = filename
                    filename_for_file = f"{filename}.pdf" if not filename.endswith('.pdf') else filename
                    print(f"[+] Filed case. URL filename: {filename_for_url}, File filename: {filename_for_file}")
            except:
                # If API call fails, treat as unfiled case
                filename_for_url = f"E{court_case_number}"  # No extension for URL
                filename_for_file = f"E{court_case_number}.pdf"  # With extension for file
                print(f"[+] API call failed, treating as unfiled case. Generated filename: {filename_for_file}")
                key = ""
                end = ""

        print(f"[+] Launching Puppeteer/Node for download... File: {filename_for_file}")
        print(f"[DEBUG] Case ID: {case_id}, Court Case Number: {court_case_number}")
        print(f"[DEBUG] URL filename (no extension): {filename_for_url}")
        print(f"[DEBUG] File filename (with extension): {filename_for_file}")
        env = {
            "FILE_NAME": filename_for_url,  # Pass filename without extension for URL
            "KEY": key,  # Pass empty string for unfiled cases
            "END": end,  # Pass empty string for unfiled cases  
            "COOKIE": auth_cookie,
            "COURT_CASE_NUMBER": str(court_case_number),
            "FK_CASE": str(case_id),
            "IS_UNFILED": "true" if (not key and not end) else "false",
        }
        
        print(f"[DEBUG] Environment variables being passed to Node.js:")
        print(f"[DEBUG] FILE_NAME: {env['FILE_NAME']}")
        print(f"[DEBUG] COURT_CASE_NUMBER: {env['COURT_CASE_NUMBER']}")
        print(f"[DEBUG] FK_CASE: {env['FK_CASE']}")
        print(f"[DEBUG] IS_UNFILED: {env['IS_UNFILED']}")
        
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
        
        # Check if PDF was actually downloaded (use filename WITH extension)
        expected_pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}\\{filename_for_file}"
        print(f"  [DEBUG] Checking for PDF at: {expected_pdf_path}")
        
        # Also check if the directory exists
        case_dir = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}"
        print(f"  [DEBUG] Case directory exists: {os.path.exists(case_dir)}")
        
        if os.path.exists(case_dir):
            files_in_dir = os.listdir(case_dir)
            print(f"  [DEBUG] Files in case directory: {files_in_dir}")
        
        if os.path.exists(expected_pdf_path):
            print(f"  [+] PDF successfully saved: {expected_pdf_path}")
            
            # Create or find case_event for this case
            cursor.execute("""
                SELECT TOP 1 id FROM docketwatch.dbo.case_events
                WHERE fk_cases = ? AND event_description = 'MAP Document Download'
                ORDER BY created_at DESC
            """, (case_id,))
            event_row = cursor.fetchone()
            
            if not event_row:
                # Create new case_event
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.case_events (
                        fk_cases, event_date, event_description, created_at
                    )
                    OUTPUT INSERTED.id
                    VALUES (?, GETDATE(), 'MAP Document Download', GETDATE())
                """, (case_id,))
                case_event_id = cursor.fetchone()[0]
                conn.commit()
                print(f"  [+] Created new case_event {case_event_id}")
            else:
                case_event_id = event_row[0]
                print(f"  [+] Using existing case_event {case_event_id}")
            
            # Create document record
            docs_created = insert_documents_for_event(cursor, case_event_id, tool_id=26)
            if docs_created > 0:
                print(f"  [+] Created {docs_created} document record(s)")
            
    
        else:
            print(f"  [!] PDF not found at expected location: {expected_pdf_path}")
            # Don't mark as completed if PDF wasn't found
        
        print(f"  [*] Finished {case_id} / {court_case_number}")

    except Exception as ex:
        print(f"  [!] Exception for case {case_id}: {ex}")

print("All pending MAP cases processed.")
