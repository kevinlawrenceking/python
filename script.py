import time
import pyodbc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import re

# **Configure ChromeDriver Path**
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

# **Configure Chrome Options**
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Hide browser
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# **Start ChromeDriver**
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)
print("ChromeDriver Initialized Successfully!")

# **Configure Database Connection**
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=10.146.177.160;"
    "DATABASE=docketwatch;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()

# **Query ALL Court/Practice Pairs**
query = """
    SELECT id, yy, fk_court, fk_practice, last_number
    FROM docketwatch.dbo.case_counter
    ORDER BY id ASC
"""
cursor.execute(query)
case_counters = cursor.fetchall()

if not case_counters:
    print("No records found in case_counter. Exiting...")
    driver.quit()
    conn.close()
    exit()

# **Process Each Court/Practice in `case_counter`**
for case_counter in case_counters:
    counter_id = case_counter[0]
    yy = str(case_counter[1])  # Year as string
    fk_court = case_counter[2]  # Court Code
    fk_practice = case_counter[3]  # Practice Code
    last_number = case_counter[4]  # Last Known Case Number

    print(f"\nSearching new cases for {fk_court}-{fk_practice}, starting from {last_number}")

    # **Loop Until "No match found"**
    while True:
        # **Generate Next Case Number**
        case_number = f"{yy}{fk_court}{fk_practice}{str(last_number).zfill(5)}"
        print(f"\nSearching for case: {case_number}")

        # **Construct the Search URL**
        case_url = f"https://www.lacourt.org/casesummary/ui/index.aspx?casetype=familylaw&casenumber={case_number}"
        driver.get(case_url)
        time.sleep(2)  # Wait for page to load
        print(f"Navigated to: {driver.current_url}")

        # **Retrieve Page Source**
        page_source = driver.page_source

        # **Check if "No match found" Exists**
        if "No match found for case number" in page_source:
            print(f"No match found for {case_number}. Stopping search for this court/practice.")
            break  # Stop searching for this courthouse/practice

        # **Extract Case Details**
        try:
            # **Extract Case Number**
            case_number_match = re.search(r"<b>Case Number:</b>&nbsp;&nbsp;</span>(.*?)<br>", page_source, re.DOTALL)
            case_number_text = case_number_match.group(1).strip() if case_number_match else "UNKNOWN"

            # **Extract Case Name**
            case_name_match = re.search(r"<b>Case Number:</b>&nbsp;&nbsp;</span>.*?<br>\s*(.*?)\s*</p>", page_source, re.DOTALL)
            case_name = case_name_match.group(1).strip() if case_name_match else "UNKNOWN"

            # **Extract Filing Date**
            filing_date_match = re.search(r"<b>Filing Date:</b>&nbsp;&nbsp;(.*?)<br>", page_source, re.DOTALL)
            filing_date = filing_date_match.group(1).strip() if filing_date_match else "UNKNOWN"

            # **Extract Case Type (Notes) and Remove '</span>'**
            case_type_match = re.search(r"<b>Case Type:</b>&nbsp;&nbsp;(.*?)<br>", page_source, re.DOTALL)
            case_type = case_type_match.group(1).replace("</span>", "").strip() if case_type_match else "UNKNOWN"

            # **Extract Status**
            status_match = re.search(r"<b>Status:</b>&nbsp;&nbsp;(.*?)<br>", page_source, re.DOTALL)
            status = status_match.group(1).strip() if status_match else "UNKNOWN"

            print(f"Case found: {case_number_text} - {case_name} ({case_type})")

            # **Insert Case into Database**
            insert_query = """
                INSERT INTO docketwatch.dbo.cases (case_number, case_name, notes, status, owner)
                SELECT ?, ?, ?, 'New', 'system'
                WHERE NOT EXISTS (
                    SELECT 1 FROM docketwatch.dbo.cases WHERE case_number = ?
                )
            """
            cursor.execute(insert_query, (case_number_text, case_name, case_type, case_number_text))
            conn.commit()

            print(f"Inserted new case: {case_number_text} - {case_name}")

            # **Increment Case Number for Next Search**
            last_number += 1

        except Exception as e:
            print(f"Error extracting details for {case_number}: {str(e)}")
            break  # Stop on any error

    # **Update `last_number` AND `last_updated` in case_counter AFTER COMPLETING SEARCH FOR THIS COURT/PRACTICE**
    update_query = """
        UPDATE docketwatch.dbo.case_counter
        SET last_number = ?, last_updated = GETDATE()
        WHERE id = ?
    """
    cursor.execute(update_query, (last_number, counter_id))
    conn.commit()
    print(f"Updated last_number to {last_number} for {fk_court}-{fk_practice}")

# **Close Database and WebDriver**
cursor.close()
conn.close()
driver.quit()

print("Script Complete!")
