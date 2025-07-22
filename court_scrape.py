import requests
from bs4 import BeautifulSoup
import pymssql
import time

# Database connection settings
DB_SERVER = "TMZTOOLSSQL"
DB_DATABASE = "docketwatch"
DB_USER = "docket_user"
DB_PASSWORD = "T1o2n3y4r5a6g7o8!"

# Base URL for court locations
BASE_URL = "https://www.lacourt.org"

# Function to insert court details
def insert_court(cursor, court_code, court_name, address, city, state, zip_code, image_location):
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM courts WHERE court_code = %s)
        INSERT INTO courts (court_code, court_name, address, city, state, zip, image_location)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (court_code, court_code, court_name, address, city, state, zip_code, image_location))

# Function to insert case counter records for each practice type
def insert_case_counter(cursor, court_code, practice_code):
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM case_counter WHERE fk_court = %s AND fk_practice = %s)
        INSERT INTO case_counter (fk_court, fk_practice, last_number)
        VALUES (%s, %s, 0)
    """, (court_code, practice_code, court_code, practice_code))

# Function to scrape and process 5 courts at a time
def scrape_courts():
    url = f"{BASE_URL}/courthouse/"
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to retrieve data")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    courts = soup.select("#siteMasterHolder_locationLeftHolder_courthouseWrap ul#chcontainer li")[:5]  # Process 5 courts at a time

    conn = pymssql.connect(DB_SERVER, DB_USER, DB_PASSWORD, DB_DATABASE)
    cursor = conn.cursor()

    for court in courts:
        try:
            court_link = court.find("a")["href"]
            court_code = court_link.split("/")[-1]  # Extract court code from URL
            court_name = court.find("a").text.strip().split("\n")[0]  # First line is court name
            address_info = court.find("a").text.strip().split("\n")[1:]  # Remaining lines are address
            address = " ".join(address_info[:-1]).strip()  # All except last line
            city_state_zip = address_info[-1].strip().split(", ")
            city = city_state_zip[0]
            state, zip_code = city_state_zip[1].split(" ")
            image_location = BASE_URL + court.find("img")["src"] if court.find("img") else None

            # Insert into courts table
            insert_court(cursor, court_code, court_name, address, city, state, zip_code, image_location)

            # Find associated practice codes (court types)
            practice_codes = [div.text.strip() for div in court.select("span div")]

            for practice_code in practice_codes:
                insert_case_counter(cursor, court_code, practice_code)

            print(f"Inserted court: {court_name} ({court_code}) with {len(practice_codes)} practices")

            # Sleep briefly to avoid hammering the site
            time.sleep(2)

        except Exception as e:
            print(f"Error processing court: {e}")

    conn.commit()
    conn.close()
    print("Scraping complete!")

# Run the scraper
scrape_courts()
