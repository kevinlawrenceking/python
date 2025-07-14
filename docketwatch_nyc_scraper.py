import os
import pyodbc
import time
import sys
import logging
import re

from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

from case_processing import process_case
from celebrity_matches import check_celebrity_matches

# === CONFIG ===
DSN = "Docketwatch"
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === DB CONNECTION ===
conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("""
    SELECT TOP 1 r.id as fk_task_run 
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
    WHERE s.filename = ? 
    ORDER BY r.id DESC
""", (script_filename,))
task_run = cursor.fetchone()
fk_task_run = task_run[0] if task_run else None

def log_message(log_type, message):
    logging.info(message)
    if fk_task_run:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?)
            """, (fk_task_run, log_type, message))
            log_id = cursor.fetchone()[0]
            conn.commit()
            return log_id
        except Exception as e:
            print(f"Log Error: {e}")
            return None

log_message("INFO", "=== New York County Case Scraper Started ===")

# === COURT SETUP ===
cursor.execute("""
    SELECT TOP 5 c.[court_code], c.[court_name], c.[court_id], co.[code] as county_code
    FROM [docketwatch].[dbo].[courts] c
    INNER JOIN [docketwatch].[dbo].[counties] co ON co.id = c.fk_county
    WHERE c.[state] = 'NY' AND c.[court_code] IS NOT NULL AND c.[court_id] <> 3
    ORDER BY ISNULL(c.last_scraped, '2000-01-01') ASC
""")
courts = cursor.fetchall()

# === UNDETECTED CHROME ===
chrome_options = uc.ChromeOptions()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--disable-gpu")
# Do NOT use headless mode

try:
    driver = uc.Chrome(options=chrome_options)
except Exception as chrome_error:
    log_message("ERROR", f"Failed to launch ChromeDriver: {chrome_error}")
    sys.exit(1)

LOGIN_URL = "https://iapps.courts.state.ny.us/nyscef/Login"
SEARCH_URL = "https://iapps.courts.state.ny.us/nyscef/CaseSearch?TAB=courtDateRange"

driver.get(LOGIN_URL)
time.sleep(10)

# === CLOUDFLARE CHECK ===
if "Just a moment" in driver.page_source or "cf_chl_opt" in driver.page_source:
    log_message("INFO", "Waiting for Cloudflare interstitial...")
    WebDriverWait(driver, 60).until_not(lambda d: "Just a moment" in d.page_source or "cf_chl_opt" in d.page_source)
    log_message("INFO", "Cloudflare challenge passed")

# === LOGIN ===
cursor.execute("SELECT nyc_user, nyc_pwd FROM docketwatch.dbo.utilities WHERE id=1")
credentials = cursor.fetchone()
if not credentials:
    log_message("ERROR", "No credentials found. Exiting...")
    sys.exit()

nyc_username, nyc_password = credentials

try:
    WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "txtUserName"))).send_keys(nyc_username)
    time.sleep(2)
    driver.find_element(By.ID, "pwPassword").send_keys(nyc_password)
    time.sleep(2)
    driver.find_element(By.ID, "btnLogin").click()
    time.sleep(5)
except Exception as login_error:
    log_message("ERROR", f"Login error: {login_error}")
    driver.quit()
    sys.exit()

# === COURT LOOP ===
for court in courts:
    court_code, court_name, court_id, county_code = court
    log_message("INFO", f"=== Scraper Started for {court_name} ({court_code}) ===")
    driver.get(SEARCH_URL)
    time.sleep(5)

    try:
        current_date = datetime.now().strftime("%m/%d/%Y")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "txtFilingDate"))).send_keys(current_date)
        Select(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "selCountyCourt")))).select_by_value(str(court_id))
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[@class='BTN_Green h-captcha']"))).click()
        time.sleep(7)

        while True:
            try:
                case_rows = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//table[@class='NewSearchResults']/tbody/tr"))
                )
                for row in case_rows:
                    try:
                        row_html = row.get_attribute("innerHTML")
                        if "*****<br>*****" in row_html:
                            log_message("INFO", f"Restricted case skipped for {court_code}")
                            continue

                        case_number_element = row.find_elements(By.XPATH, ".//td[1]/a")
                        if case_number_element:
                            case_number_link = case_number_element[0]
                            case_number = case_number_link.text.strip()
                            case_url = case_number_link.get_attribute("href")
                        else:
                            case_number = row.find_element(By.XPATH, ".//td[1]").text.split("\n")[0].strip()
                            case_url = None

                        received_date = row.find_element(By.XPATH, ".//td[1]").text.split("\n")[-1].strip()
                        case_name = row.find_element(By.XPATH, ".//td[3]").text.strip()
                        case_status = row.find_element(By.XPATH, ".//td[2]/span").text.strip()
                        case_type = row.find_element(By.XPATH, ".//td[4]/span").text.strip()

                        cursor.execute(
                            "SELECT COUNT(*) FROM docketwatch.dbo.cases WHERE case_number = ? AND case_name = ?",
                            (case_number, case_name)
                        )
                        exists = cursor.fetchone()[0]

                        if not exists:
                            log_id = log_message("INFO", f"Inserted and processed case: {case_name} for {court_code}")
                            insert_query = """
                                INSERT INTO docketwatch.dbo.cases 
                                (case_url, case_number, case_name, received_date, fk_court, case_type, case_status, efile_status, status, owner, fk_task_run_log)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Review', 'system', ?)
                            """
                            cursor.execute(insert_query, (
                                case_url, case_number, case_name, received_date, court_code,
                                case_type, case_status, "", log_id))
                            conn.commit()
                            process_case(None, case_number, case_name, court_code, county_code)
                        else:
                            log_message("INFO", f"Case already exists: {case_name} ({case_number}) for {court_code}")

                    except Exception as row_error:
                        log_message("ERROR", f"Error processing row for {court_code}: {str(row_error)}")
                        continue

                try:
                    driver.find_element(By.XPATH, "//a[contains(text(), '>>')]").click()
                    time.sleep(5)
                except Exception:
                    log_message("INFO", f"No more pages found for {court_code}. Updating timestamp.")
                    cursor.execute("UPDATE docketwatch.dbo.courts SET last_scraped = GETDATE() WHERE court_code = ?", (court_code,))
                    conn.commit()
                    break

            except Exception as e:
                if not str(e).strip():
                    log_message("INFO", f"No new cases found for {court_code} today.")
                else:
                    log_message("ERROR", f"Error scraping {court_code}: {str(e)}")
                break


    except Exception as fatal_error:
        log_message("ERROR", f"Fatal error for court {court_code}: {str(fatal_error)}")

log_message("INFO", "=== NYC Court Scraper Complete ===")
driver.quit()
