import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

if len(sys.argv) < 4:
    print("Usage: python capture_pdf_viewer.py <DocumentName> <Key> <EndTicks>")
    sys.exit(1)

name = sys.argv[1]  # e.g., E745292680
key = sys.argv[2]
end = sys.argv[3]

url = f"https://ww2.lacourt.org/documentviewer/v1/?name={name}&key={key}&end={end}"

print(f"Opening viewer URL: {url}")

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
chrome_options = Options()
# Comment out headless mode for visual testing
# chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--start-maximized")

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    driver.get(url)

    # Wait for iframe or viewer element (you may adjust this)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
    )

    time.sleep(3)  # let PDF render fully

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = rf"\\10.146.176.84\general\docketwatch\pdf_captures\{name}_{timestamp}.png"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    driver.save_screenshot(filename)
    print(f"Screenshot saved: {filename}")

except Exception as e:
    print(f"Error capturing viewer: {e}")

finally:
    driver.quit()
