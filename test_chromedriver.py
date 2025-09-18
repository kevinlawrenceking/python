"""
Test script to verify ChromeDriver is working properly
"""
import uuid, tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"

def test_chromedriver():
    print("Testing ChromeDriver setup...")
    
    try:
        # Create unique user data directory to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        temp_user_data_dir = os.path.join(tempfile.gettempdir(), f"chrome_user_data_{unique_id}")
        
        # Setup Chrome options (same as production scripts)
        opts = Options()
        # opts.add_argument("--headless=new")  # Commented out due to Chrome compatibility issues
        opts.add_argument("--headless")  # Use stable headless mode
        opts.add_argument("--disable-gpu") 
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-plugins")
        opts.add_argument("--disable-images")
        opts.add_argument(f"--user-data-dir={temp_user_data_dir}")
        opts.add_argument("--disable-web-security")
        opts.add_argument("--allow-running-insecure-content")
        
        print("Creating ChromeDriver instance...")
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=opts)
        
        print("Testing navigation...")
        driver.get("https://www.google.com")
        
        print(f"Page title: {driver.title}")
        print(f"Page URL: {driver.current_url}")
        
        driver.quit()
        print("SUCCESS: ChromeDriver test completed successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR: ChromeDriver test failed: {e}")
        return False

if __name__ == "__main__":
    test_chromedriver()