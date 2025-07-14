import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === ChromeDriver setup ===
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Logging into media.lacourt.org...")
    driver.get("https://media.lacourt.org/Identity/Account/Login")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys("priscilla.hwang@tmz.com")
    driver.find_element(By.ID, "password").send_keys("P12isci11@")
    driver.find_element(By.ID, "next").click()

    # Wait for redirect to dashboard
    WebDriverWait(driver, 30).until(EC.url_contains("media.lacourt.org"))
    print("Login successful.")

    # Navigate to unfiled complaints page
    print("Opening unfiled complaints table...")
    driver.get("https://media.lacourt.org/#/unfiledcomplaints")

    # Wait up to 60 seconds for the table to render
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.k-grid-table"))
    )
    print("Table loaded.")

    # Find all view buttons
    view_buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn.btn-info")

    if not view_buttons:
        print("No view buttons found.")
    else:
        print(f"Found {len(view_buttons)} rows. Clicking first view button...")
        view_buttons[0].click()

        # Wait for new tab to open
        time.sleep(3)
        tabs = driver.window_handles
        if len(tabs) > 1:
            driver.switch_to.window(tabs[1])
            print("Switched to viewer tab.")
            time.sleep(3)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = rf"\\10.146.176.84\general\docketwatch\pdf_captures\unfiled_{timestamp}.png"
            driver.save_screenshot(filename)
            print(f"PDF screenshot saved to {filename}")
        else:
            print("No new tab detected.")

except Exception as e:
    print(f"Error: {e}")

finally:
    driver.quit()
