import time
import pyodbc
import re
import os
import sys
import logging
import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

from case_processing import process_case  # process_case(case_id, case_number, case_name, court_code, county_code)
from celebrity_matches import check_celebrity_matches

# === Configure Database Connection ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# === Fetch All New York County Courts ===
cursor.execute("""
    SELECT c.[court_code], c.[court_name], c.[court_id], co.[code] as county_code
    FROM [docketwatch].[dbo].[courts] c
    INNER JOIN [dbo].[counties] co ON co.id = c.fk_county
    WHERE c.[state] = 'NY' AND c.[court_code] IS NOT NULL
""")

courts = cursor.fetchall()

# === Start ChromeDriver ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# === Login to NYSCEF Once ===
LOGIN_URL = "https://iapps.courts.state.ny.us/nyscef/Login"
SEARCH_URL = "https://iapps.courts.state.ny.us/nyscef/CaseSearch?TAB=courtDateRange"

driver.get(LOGIN_URL)
time.sleep(5)
cursor.execute("SELECT nyc_user, nyc_pwd FROM docketwatch.dbo.utilities WHERE id=1")
credentials = cursor.fetchone()
if not credentials:
    logging.error("No credentials found. Exiting...")
    sys.exit()
nyc_username, nyc_password = credentials
WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "txtUserName"))).send_keys(nyc_username)
time.sleep(3)
WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "pwPassword"))).send_keys(nyc_password)
time.sleep(3)
WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "btnLogin"))).click()
time.sleep(5)

for court in courts:
    court_code, court_name, court_id, county_code = court
    
    # === Configure Logging Per Court ===
    LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_{court_code}_scraper.log"
    logger = logging.getLogger(f"scraper_{court_code}")
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, mode='a')
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    if not logger.hasHandlers():
        logger.addHandler(file_handler)
    logger.info(f"=== Scraper Started for {court_name} ({court_code}) ===")
    
    driver.get(SEARCH_URL)
    time.sleep(5)
    
    try:
        # === Enter Today’s Date ===
        current_date = datetime.now().strftime("%m/%d/%Y")
        date_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "txtFilingDate")))
        date_input.send_keys(current_date)
        time.sleep(1)
    
        # === Select Court ===
        court_select = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "selCountyCourt")))
        Select(court_select).select_by_value(str(court_id))
        time.sleep(2)
    
        # === Click "Search" ===
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[@class='BTN_Green h-captcha']"))).click()
        time.sleep(7)
    
        # === Scrape Case Results ===
        while True:
            try:
                case_rows = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//table[@class='NewSearchResults']/tbody/tr"))
                )
                for row in case_rows:
                    case_number_link = row.find_element(By.XPATH, ".//td[1]/a")
                    case_number = case_number_link.text.strip()
                    case_url = case_number_link.get_attribute("href")
                    received_date = row.find_element(By.XPATH, ".//td[1]").text.split("\n")[-1].strip()
                    case_name = row.find_element(By.XPATH, ".//td[3]").text.strip()
                    case_status = row.find_element(By.XPATH, ".//td[2]/span").text.strip()
                    case_type = row.find_element(By.XPATH, ".//td[4]/span").text.strip()
                    
                    insert_query = """
                        INSERT INTO docketwatch.dbo.cases 
                        (case_url, case_number, case_name, received_date, fk_court, case_type, case_status, efile_status, status, owner)
                        SELECT ?, ?, ?, ?, ?, ?, ?, ?, 'Review', 'system'
                        WHERE NOT EXISTS (
                            SELECT 1 FROM docketwatch.dbo.cases WHERE case_name = ? AND fk_court = ?
                        )
                    """
                    insert_values = (case_url, case_number, case_name, received_date, court_code, case_type, case_status, "", case_name, court_code)
                    
                    test_query = insert_query.replace("?", "'{}'").format(*insert_values)
                    logger.info(f"Testing SQL Execution for {court_code}: {test_query}")
                    
                    cursor.execute(insert_query, insert_values)
                    conn.commit()
                    
                    process_case(None, case_number, case_name, court_code, county_code)
                    logger.info(f"Inserted and processed case: {case_name} for {court_code}")
                
                # Next Page
                try:
                    next_page = driver.find_element(By.XPATH, "//a[contains(text(), '>>')]")
                    next_page.click()
                    time.sleep(5)
                except Exception:
                    break
            except Exception as e:
                logger.error(f"Error scraping cases for {court_code}: {str(e)}")
                break
        
        logger.info(f"=== Scraper Completed for {court_name} ({court_code}) ===")
    
    except Exception as e:
        logger.error(f"Error processing {court_name} ({court_code}): {str(e)}")
    
    # Cleanup logger handlers to avoid duplicate logs
    logger.handlers.clear()

# === Final Cleanup ===
cursor.close()
conn.close()
driver.quit()
logging.info("=== All New York County Scrapers Completed ===")
