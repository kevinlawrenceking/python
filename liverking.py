import time
import os
import sys
import pyodbc
import logging
import requests
from email.mime.text import MIMEText
import smtplib
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === CONFIG ===
NAMES_TO_SEARCH = [
    "Rogan",
    "Rogan, Joeseph",
    "Rogan, Joeseph James",
    "Johnson, Brian"
]

FROM_EMAIL = "it@tmz.com"
TO_EMAIL = "kevin.king@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

SEARCH_URL = "https://odysseyweb.traviscountytx.gov/Portal"
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === DB Setup ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
conn.setencoding(encoding='utf-8')
cursor = conn.cursor()

cursor.execute("""
    SELECT TOP 1 r.id
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
    WHERE s.filename = ?
    ORDER BY r.id DESC
""", (script_filename,))
row = cursor.fetchone()
fk_task_run = row[0] if row else None

def log_message(log_type, message):
    logging.info(message)
    if fk_task_run:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?)
            """, (fk_task_run, log_type, message))
            conn.commit()
        except:
            pass

cursor.execute("SELECT captcha_api FROM docketwatch.dbo.utilities WHERE id = 1")
captcha_api_key = cursor.fetchone()[0]

# === CAPTCHA Solver ===
def solve_recaptcha(api_key, sitekey, page_url):
    payload = {
        'key': api_key,
        'method': 'userrecaptcha',
        'googlekey': sitekey,
        'pageurl': page_url,
        'json': 1
    }
    resp = requests.post("http://2captcha.com/in.php", data=payload).json()
    if resp.get("status") != 1:
        raise Exception("2Captcha submit failed: " + str(resp))

    captcha_id = resp["request"]
    for _ in range(30):
        time.sleep(3)
        result = requests.get(f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1").json()
        if result.get("status") == 1:
            return result["request"]
    raise Exception("2Captcha timeout")

# === Email Sender ===
def send_alert_email(name):
    msg = MIMEText(f"A case result was found for search string: {name}\n\n{SEARCH_URL}")
    msg["Subject"] = f"Travis County Case Match: {name}"
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.sendmail(FROM_EMAIL, [TO_EMAIL], msg.as_string())

# === MAIN ===
def main():
    opts = Options()
    ##opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)

    try:
        driver.get(SEARCH_URL)

        # Click Smart Search
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/Portal/Home/Dashboard/29']"))
        ).click()

        for name in NAMES_TO_SEARCH:
            try:
                # Wait for and enter the name
                input_box = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "caseCriteria_SearchCriteria"))
                )
                input_box.clear()
                input_box.send_keys(name)

                # Solve CAPTCHA for this name
                recaptcha_div = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "g-recaptcha"))
                )
                sitekey = recaptcha_div.get_attribute("data-sitekey")
                token = solve_recaptcha(captcha_api_key, sitekey, driver.current_url)

                driver.execute_script("document.getElementById('g-recaptcha-response').style.display = 'block';")
                driver.execute_script("document.getElementById('g-recaptcha-response').value = arguments[0];", token)
                time.sleep(2)

                # Submit
                driver.find_element(By.ID, "btnSSSubmit").click()
                time.sleep(5)

                if "No cases match your search" in driver.page_source:
                    log_message("INFO", f"No match for: {name}")
                else:
                    log_message("ALERT", f"Match FOUND for: {name}")
                    send_alert_email(name)

                # Reset back to Smart Search tab
                try:
                    driver.find_element(By.ID, "tcControllerLink_0").click()
                    time.sleep(1)
                except:
                    pass

            except Exception as e:
                log_message("ERROR", f"Error processing name '{name}': {e}")

    finally:
        driver.quit()
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
