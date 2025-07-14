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

# ** Configure Logging **
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_westchester_scraper.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("=== Westchester Surrogate's Court File Search Started ===")

# ** Prevent Multiple Script Instances **
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_westchester_scraper.lock"

def is_another_instance_running():
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "r") as f:
            try:
                pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    return True
            except ValueError:
                pass
        os.remove(LOCK_FILE)
    return False

if is_another_instance_running():
    logging.error("Another instance is already running. Exiting...")
    sys.exit()
else:
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

try:
    # ** Start ChromeDriver **
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    # REMOVE HEADLESS MODE FOR DEBUGGING
    # chrome_options.add_argument("--headless=new")  # Commented out for debugging
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    logging.info("ChromeDriver Initialized Successfully")

    # ** Connect to Database **
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    # ** Fetch Username & Password from Database **
    try:
        cursor.execute("SELECT nyc_user, nyc_pwd FROM docketwatch.dbo.utilities WHERE id=1")
        credentials = cursor.fetchone()
        
        if not credentials:
            logging.error("No credentials found in database. Exiting...")
            driver.quit()
            conn.close()
            sys.exit()
        
        nyc_username, nyc_password = credentials
        logging.info("Retrieved login credentials from database.")

    except Exception as e:
        logging.error(f"Error fetching credentials: {str(e)}")
        driver.quit()
        conn.close()
        sys.exit()

    # ** Login to NYSCEF **
    LOGIN_URL = "https://iapps.courts.state.ny.us/nyscef/Login"
    driver.get(LOGIN_URL)
    time.sleep(5)

    try:
        username_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "txtUserName"))
        )
        username_input.send_keys(nyc_username)

        password_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "pwPassword"))
        )
        password_input.send_keys(nyc_password)

        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "btnLogin"))
        )
        login_button.click()
        
        logging.info("Logged in successfully.")
        time.sleep(5)  # Wait for dashboard to load

    except Exception as e:
        logging.error(f"Failed to log in: {str(e)}")
        driver.quit()
        sys.exit()

    # ** Navigate to Surrogate's Court File Search Page **
    SEARCH_URL = "https://iapps.courts.state.ny.us/nyscef/SurrogatesFileRecordSearch"
    driver.get(SEARCH_URL)
    time.sleep(5)  # Allow page to load

    # ** Select Court - Westchester County Surrogate's Court **
    try:
        court_value = "PAnNtnns4JN8a4N80UWTYg=="  # Westchester County Surrogate's Court
        court_select = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "selCourt"))
        )

        # Use JavaScript to set the value and trigger the change event
        driver.execute_script(f"arguments[0].value = '{court_value}';", court_select)
        time.sleep(2)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", court_select)

        logging.info("Successfully selected Westchester County Surrogate's Court.")
        time.sleep(3)  # Allow change to register

    except Exception as e:
        logging.error(f"Failed to select court dropdown: {str(e)}")
        driver.quit()
        sys.exit()

    # ** Enter Party Name **
    try:
        first_name_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.NAME, "txtFirstName"))
        )
        first_name_input.send_keys("Michelle")

        last_name_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.NAME, "txtLastName"))
        )
        last_name_input.send_keys("Trachtenberg")

        logging.info("Entered name: Michelle Trachtenberg")
        time.sleep(2)

    except Exception as e:
        logging.error(f"Failed to enter name: {str(e)}")
        driver.quit()
        sys.exit()

    # ** Click "Search" Button **
    try:
        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.NAME, "btnSearch"))
        )
        search_button.click()
        time.sleep(5)  # Wait for search results
        logging.info("Search executed successfully.")

    except Exception as e:
        logging.error(f"Failed to click 'Search' button: {str(e)}")
        driver.quit()
        sys.exit()

    # ** Check if File Records Were Found **
    try:
        no_records = driver.find_elements(By.XPATH, "//td[contains(text(), 'No File Records Found')]")
        if no_records:
            logging.info("No records found.")
        else:
            # ** Extract File Records **
            file_rows = driver.find_elements(By.XPATH, "//table[@class='dataList']/tbody/tr")
            
            for row in file_rows:
                columns = row.find_elements(By.TAG_NAME, "td")
                if len(columns) < 4:
                    continue  # Skip malformed rows
                
                file_no = columns[0].text.strip()
                file_name = columns[1].text.strip()
                dob_dod = columns[2].text.strip()
                address = columns[3].text.strip()

                # Insert record into database
                insert_query = """
                    INSERT INTO docketwatch.dbo.records_tmp (file_no, file_name, dob_dod, address)
                    SELECT ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM docketwatch.dbo.records_tmp WHERE file_no = ?
                    )
                """
                cursor.execute(insert_query, (file_no, file_name, dob_dod, address, file_no))
                conn.commit()
                logging.info(f"Inserted record: {file_no} - {file_name}")

    except Exception as e:
        logging.error(f"Error processing search results: {str(e)}")

    # ** Cleanup and Exit **
    cursor.close()
    conn.close()
    driver.quit()
    os.remove(LOCK_FILE)
    logging.info("Westchester Surrogate's Court File Search Completed Successfully!")

except Exception as e:
    logging.error(f"Script Failed: {str(e)}")
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    sys.exit(1)
