import subprocess
import re
import os
import sys
import time
import json
import base64
import pyodbc
import requests
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === Get date param from command line ===
if len(sys.argv) < 2:
    print("Usage: python docketwatch_map_unfiled_scraper.py MM-DD-YYYY")
    sys.exit(1)

input_date = sys.argv[1]
try:
    dt = datetime.strptime(input_date, "%m-%d-%Y")
    date_for_url = dt.strftime("%m-%d-%Y")
    folder_date = dt.strftime("%Y%m%d")
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

# === Setup ChromeDriver with download support ===
download_dir = r"\\10.146.176.84\general\docketwatch\pdf_captures"
CHROMEDRIVER_PATH = "C:\\WebDriver\\chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
})
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# === Step 1: Log into media.lacourt.org ===
auth_cookie = None
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
        cookies = driver.get_cookies()
        cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
        auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
    else:
        print(f"Login failed. Current URL: {driver.current_url}")
        driver.quit()
        sys.exit(1)

except Exception as e:
    print(f"Login failed: {e}")
    driver.quit()
    sys.exit(1)

# === Step 2: Navigate to unfiled complaints and click view buttons ===
try:
    driver.get("https://media.lacourt.org/#/unfiledcomplaints")
    print("Waiting for case table to load...")
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.k-grid-table"))
    )
    print("Case table loaded.")

    view_buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn.btn-info")

    if not view_buttons:
        print("No View buttons found.")
    else:
        print(f"Found {len(view_buttons)} cases. Clicking the first one...")
        view_buttons[0].click()

        time.sleep(3)
        tabs = driver.window_handles
        if len(tabs) > 1:
            driver.switch_to.window(tabs[1])
            time.sleep(3)

            print("Waiting for viewer JS object to become available...")
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script("""
                        try {
                            return typeof Atalasoft !== 'undefined' &&
                                   Atalasoft.Controls &&
                                   Atalasoft.Controls.WebDocumentViewer &&
                                   Atalasoft.Controls.WebDocumentViewer._viewerInstances &&
                                   Atalasoft.Controls.WebDocumentViewer._viewerInstances.length > 0;
                        } catch (err) {
                            return false;
                        }
                    """)
                )
            except Exception as e:
                print(f"Viewer JS object did not become ready: {e}")
                screenshot_path = os.path.join(download_dir, "viewer_error.png")
                driver.save_screenshot(screenshot_path)
                print(f"Screenshot saved to: {screenshot_path}")
                raise

            print("Rendering full viewer page as PDF...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_path = os.path.join(download_dir, f"unfiled_capture_{timestamp}.pdf")

            try:
                result = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
                with open(pdf_path, "wb") as f:
                    f.write(base64.b64decode(result["data"]))
                print(f"PDF saved to: {pdf_path}")
            except Exception as e:
                print(f"Failed to render PDF: {e}")

        else:
            print("Viewer tab did not open.")

except Exception as e:
    print(f"Error during case table interaction: {e}")

finally:
    driver.quit()
