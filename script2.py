import time
import pyodbc
import re
import os
import sys
import logging
import psutil  # Added to check running processes
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from datetime import datetime

# ** Configure Logging **
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_scraper.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("=== Script Started ===")

# ** Ensure Only One Instance is Running**
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_scraper.lock"

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
    # ** Configure ChromeDriver Path **
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-features=UseChromeMLModelLoader")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    logging.info("ChromeDriver Initialized Successfully")

    # ** Database Connection using DSN **
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    # ** Query ALL Court/Practice Pairs **
    query = """
        SELECT id, yy, fk_court, fk_practice, last_number, last_updated
        FROM docketwatch.dbo.case_counter
        ORDER BY id ASC
    """
    cursor.execute(query)
    case_counters = cursor.fetchall()

    if not case_counters:
        logging.warning("No records found in case_counter. Exiting...")
        driver.quit()
        conn.close()
        os.remove(LOCK_FILE)
        sys.exit()

    # ** Process Each Court/Practice in `case_counter` **
    for case_counter in case_counters:
        counter_id, yy, fk_court, fk_practice, last_number, _ = case_counter
        yy = str(yy)

        logging.info(f"Searching new cases for {fk_court}-{fk_practice}, starting from {last_number}")

        while True:
            case_number = f"{yy}{fk_court}{fk_practice}{str(last_number).zfill(5)}"
            case_url = f"https://www.lacourt.org/casesummary/ui/index.aspx?casetype=familylaw&casenumber={case_number}"
            driver.get(case_url)
            time.sleep(3)

            page_source = driver.page_source
            if "No match found for case number" in page_source:
                logging.info(f"No match found for {case_number}. Stopping search for this court/practice.")
                break

            try:
                case_number_match = re.search(r"<b>Case Number:</b>&nbsp;&nbsp;</span>(.*?)<br>", page_source, re.DOTALL)
                case_number_text = case_number_match.group(1).strip() if case_number_match else "UNKNOWN"

                case_name_match = re.search(r"<b>Case Number:</b>&nbsp;&nbsp;</span>.*?<br>\s*(.*?)\s*</p>", page_source, re.DOTALL)
                case_name = case_name_match.group(1).strip() if case_name_match else "UNKNOWN"

                case_type_match = re.search(r"<b>Case Type:</b>&nbsp;&nbsp;(.*?)<br>", page_source, re.DOTALL)
                case_type = case_type_match.group(1).replace("</span>", "").strip() if case_type_match else "UNKNOWN"

                insert_query = """
                    INSERT INTO docketwatch.dbo.cases (case_number, case_name, notes, status, owner)
                    SELECT ?, ?, ?, 'New', 'system'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM docketwatch.dbo.cases WHERE case_number = ?
                    )
                """
                cursor.execute(insert_query, (case_number_text, case_name, case_type, case_number_text))
                conn.commit()
                last_number += 1

            except Exception as e:
                logging.error(f"Error extracting details for {case_number}: {str(e)}")
                break

        update_query = "UPDATE docketwatch.dbo.case_counter SET last_number = ?, last_updated = GETDATE() WHERE id = ?"
        cursor.execute(update_query, (last_number, counter_id))
        conn.commit()

    # ** ADD PARTY PROCESSING & CELEBRITY MATCHING BELOW **

    def clean_case_name(case_name):
        cleaned_name = re.sub(r"(Approval Of Minor'S Contract - |Joint Petition Of:|Trust, Dated.*|As Amended)", "", case_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()
        return cleaned_name

    def process_cases():
        cursor.execute("SELECT id, case_number, case_name FROM docketwatch.dbo.cases WHERE case_parties_checked = 0 ORDER BY id ASC")
        cases = cursor.fetchall()

        for case in cases:
            case_id, case_number, case_name = case
            case_name = clean_case_name(case_name)

            normalized_case_name = re.sub(r"\s(VS\.?|AND)\s", "|", case_name, flags=re.IGNORECASE)
            parties = list(set(normalized_case_name.split("|")))

            for party in parties:
                party = party.strip()
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.case_parties (fk_case, party_name, party_role)
                    SELECT ?, ?, 'Party'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM docketwatch.dbo.case_parties WHERE fk_case = ? AND party_name = ?
                    )
                """, (case_id, party, case_id, party))
        
            cursor.execute("UPDATE docketwatch.dbo.cases SET case_parties_checked = 1 WHERE id = ?", (case_id,))
        
        conn.commit()

    def match_celebrities():
        cursor.execute("""
            SELECT id, case_number, case_name FROM docketwatch.dbo.cases WHERE celebrity_checked = 0 ORDER BY id ASC
        """)
        cases = cursor.fetchall()

        cursor.execute("""
            SELECT c.id AS fk_celebrity, COALESCE(a.name, c.name) AS celeb_name
            FROM docketwatch.dbo.celebrities c
            LEFT JOIN docketwatch.dbo.celebrity_names a ON a.fk_celebrity = c.id AND a.ignore != 1
            WHERE c.ignore = 0
        """)
        celebrities = cursor.fetchall()

        for case in cases:
            case_id = case[0]
            cursor.execute("SELECT party_name FROM docketwatch.dbo.case_parties WHERE fk_case = ?", (case_id,))
            case_parties = [row[0] for row in cursor.fetchall()]

            for party in case_parties:
                for celeb_id, celeb_name in celebrities:
                    if party.lower() in celeb_name.lower():
                        cursor.execute("""
                            INSERT INTO docketwatch.dbo.case_celebrity_matches (fk_case, fk_celebrity, celebrity_name, match_status)
                            SELECT ?, ?, ?, 'PARTIAL'
                            WHERE NOT EXISTS (
                                SELECT 1 FROM docketwatch.dbo.case_celebrity_matches WHERE fk_case = ? AND fk_celebrity = ? AND match_status <> 'Removed'
                            )
                        """, (case_id, celeb_id, celeb_name, case_id, celeb_id))

        conn.commit()

    process_cases()
    match_celebrities()

    cursor.close()
    conn.close()
    driver.quit()
    os.remove(LOCK_FILE)
    logging.info("Script Complete!")
