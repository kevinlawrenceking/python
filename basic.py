import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

# **Navigate to the Page**
url = "https://media.lacourt.org/lascmediaproxy/#/casecalendar"
driver.get(url)
time.sleep(5)  # Allow time for page load
print("Page loaded successfully.")

try:
    # **Find the Form Element**
    form = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//form[@name='caseCalendarForm']"))
    )

    # **Submit the Form**
    driver.execute_script("arguments[0].submit();", form)
    print("Form submitted successfully.")

    # **Wait for Results to Load**
    time.sleep(5)

except Exception as e:
    print(f"Error submitting the form: {e}")

# **Capture the Page Source After Submitting**
page_source = driver.page_source

# **Save the Output for Debugging**
with open("output_after_submit.html", "w", encoding="utf-8") as f:
    f.write(page_source)

print("Saved output_after_submit.html with the page source after form submission.")

# **Close Browser**
driver.quit()
