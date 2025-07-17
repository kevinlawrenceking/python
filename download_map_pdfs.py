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
      AND (status IS NULL OR status NOT IN ('Completed', 'Downloaded', 'Processed'))
      and id = 184633
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
                    filename = f"E{court_case_number}.pdf"
                    print(f"[+] Unfiled case detected. Generated filename: {filename}")
                    key = ""
                    end = ""
                elif filename and not filename.endswith('.pdf'):
                    # Ensure API filename has .pdf extension
                    filename = f"{filename}.pdf"
                    print(f"[+] Added .pdf extension to API filename: {filename}")
            except:
                # If API call fails, treat as unfiled case
                filename = f"E{court_case_number}.pdf"
                print(f"[+] API call failed, treating as unfiled case. Generated filename: {filename}")
                key = ""
                end = ""

        print(f"[+] Launching Puppeteer/Node for download... File: {filename}")
        print(f"[DEBUG] Case ID: {case_id}, Court Case Number: {court_case_number}")
        env = {
            "FILE_NAME": filename,
            "KEY": key if key else "UNFILED",  # Provide placeholder for unfiled cases
            "END": end if end else "UNFILED",  # Provide placeholder for unfiled cases
            "COOKIE": auth_cookie,
            "COURT_CASE_NUMBER": str(court_case_number),  # Pass actual court case number for PDF filename
            "FK_CASE": str(case_id),  # Pass case ID for folder structure
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
        
        # Check if PDF was actually downloaded (adjust path as needed)
        expected_pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}\\{filename}"
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
            print(f"  [DEBUG] About to call insert_documents_for_event with:")
            print(f"  [DEBUG] case_event_id: {case_event_id}")
            print(f"  [DEBUG] tool_id: 26")
            print(f"  [DEBUG] Expected case directory: {case_dir}")
            
            # List all files in the case directory before calling insert function
            if os.path.exists(case_dir):
                all_files = os.listdir(case_dir)
                pdf_files = [f for f in all_files if f.endswith('.pdf')]
                print(f"  [DEBUG] All files in case dir: {all_files}")
                print(f"  [DEBUG] PDF files found: {pdf_files}")
            
            docs_created = insert_documents_for_event(cursor, case_event_id, tool_id=26)
            print(f"  [DEBUG] insert_documents_for_event returned: {docs_created}")
            if docs_created > 0:
                print(f"  [+] Created {docs_created} document record(s)")
            else:
                print(f"  [!] No document records were created")
                
                # Check if the function is looking in the right place
                print(f"  [DEBUG] Checking if insert_documents_for_event can find files...")
                
            # Mark case as completed
            cursor.execute("""
                UPDATE [docketwatch].[dbo].[cases]
                SET status = 'Downloaded'
                WHERE id = ?
            """, (case_id,))
            conn.commit()
            print(f"  [+] Case {case_id} marked as Downloaded")
        else:
            print(f"  [!] PDF not found at expected location: {expected_pdf_path}")
            # Don't mark as completed if PDF wasn't found
        
        print(f"  [*] Finished {case_id} / {court_case_number}")

    except Exception as ex:
        print(f"  [!] Exception for case {case_id}: {ex}")

print("All pending MAP cases processed.")
