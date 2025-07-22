import time
import pyodbc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
from datetime import datetime

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

# **Open the NYSCEF Case Search page**
driver.get("https://iapps.courts.state.ny.us/nyscef/CaseSearch")
time.sleep(3)  # Allow time for page to load

# **Login Process**
driver.find_element(By.ID, "txtUserName").send_keys("unjdelgado3")
time.sleep(1)

driver.find_element(By.ID, "pwPassword").send_keys("TMZCourt25!")
time.sleep(1)

driver.find_element(By.ID, "btnLogin").click()
time.sleep(5)  # Wait for the dashboard to load

# **Navigate to Case Search**
driver.find_element(By.XPATH, '//a[contains(text(), "Case Search")]').click()
time.sleep(3)  # Allow search page to load

# **Click "New Cases" Tab**
driver.find_element(By.XPATH, '//span[contains(text(), "New Cases")]').click()
time.sleep(3)

# **Select Court Dropdown**
court_dropdown = Select(driver.find_element(By.ID, "selCountyCourt"))
court_dropdown.select_by_value("3")  # Selecting "New York County Supreme Court"
time.sleep(2)

# **Enter Date**
current_date = datetime.now().strftime("%m/%d/%Y")  # Format as MM/DD/YYYY
date_input = driver.find_element(By.ID, "txtFilingDate")
date_input.click()
time.sleep(1)
date_input.send_keys(current_date)  # Always uses today's date
time.sleep(1)

# **Click Search Button**
driver.find_element(By.XPATH, '//button[@class="BTN_Green h-captcha"]').click()
time.sleep(5)  # Allow results to load

# **Function to check if case exists in the database**
def case_exists(case_number):
    cursor.execute("SELECT COUNT(*) FROM cases WHERE case_number = ?", case_number)
    return cursor.fetchone()[0] > 0

# **Loop through all pages and scrape cases**
while True:
    soup = BeautifulSoup(driver.page_source, "html.parser")
    case_rows = soup.select("table tr")[1:]  # Skip header row

    for row in case_rows:
        cols = row.find_all("td")

        # **Case Received Date, Case Number & Case URL**
        case_number_link = cols[0].find("a")
        if case_number_link:
            case_number = case_number_link.text.strip()
            case_url = "https://iapps.courts.state.ny.us/nyscef/" + case_number_link["href"]
        else:
            case_number = "Not Assigned"
            case_url = None

        received_date = cols[0].find_all("br")[-1].next_sibling.strip()

        # **eFiling Status & Case Status**
        efile_status = cols[1].contents[0].strip()
        case_status = cols[1].find("span", class_="grayItalic").text.strip() if cols[1].find("span") else ""

        # **Case Name (Caption)**
        case_name = cols[2].text.strip()

        # **Court & Case Type**
        fk_court = "NYCSC"  # Hardcoded for NY County Supreme Court
        case_type = cols[3].find("span", class_="grayItalic").text.strip() if cols[3].find("span") else ""

        # **Insert only if case does not already exist**
        if not case_exists(case_number):
            cursor.execute(
                """
                INSERT INTO cases (case_number, case_name, received_date, status, owner, created_at, last_updated, 
                                  case_parties_checked, celebrity_checked, fk_court, case_type, case_status, efile_status)
                VALUES (?, ?, ?, 'New', 'System', GETDATE(), GETDATE(), 0, 0, ?, ?, ?, ?)
                """,
                case_number, case_name, received_date, fk_court, case_type, case_status, efile_status
            )
            conn.commit()

    # **Check for pagination and go to next page if available**
    next_page = driver.find_elements(By.XPATH, '//span[@class="pageNumbers"]/a[contains(text(), ">")]')
    if next_page:
        next_page[0].click()
        time.sleep(5)  # Wait for new page to load
    else:
        break  # Exit loop if no more pages

# **Close the browser and database connection**
driver.quit()
conn.close()

print("Scraping complete. All new cases added to the database.")
