import pyodbc
import requests
import logging
import time

# Setup Logging
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\\la_court_scraper.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Database Connection
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
try:
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    logging.info("Connected to DocketWatch database successfully.")
except Exception as e:
    logging.error(f"Error connecting to database: {e}")
    exit(1)

# Court case URL (placeholder for real API or scraping source)
COURT_URL_TEMPLATE = "https://lacourt.org/casesearch/{case_number}"

# Retrieve last tracked case number per court/practice
query = "SELECT fk_court, fk_practice, last_number FROM docketwatch.dbo.case_counter"
cursor.execute(query)
court_cases = cursor.fetchall()

def check_case_exists(case_number):
    """Simulates a request to check if a case exists."""
    url = COURT_URL_TEMPLATE.format(case_number=case_number)
    response = requests.get(url)
    return response.status_code == 200

def match_celebrities(case_number):
    """Matches cases with known celebrities in DocketWatch."""
    try:
        cursor.execute("""
            SELECT id, name FROM docketwatch.dbo.celebrities
        ""
        )
        celebrities = cursor.fetchall()
        
        matched_celebs = []
        for celeb_id, celeb_name in celebrities:
            if celeb_name.lower() in case_number.lower():
                matched_celebs.append((case_number, celeb_id))
                
        for case_num, celeb_id in matched_celebs:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_celebrities (fk_case, fk_celebrity)
                SELECT ?, ? WHERE NOT EXISTS (
                    SELECT 1 FROM docketwatch.dbo.case_celebrities WHERE fk_case = ? AND fk_celebrity = ?
                )
            """, (case_num, celeb_id, case_num, celeb_id))
            conn.commit()
            logging.info(f"Matched celebrity {celeb_id} with case {case_num}")
    except Exception as e:
        logging.error(f"Error matching celebrities: {e}")

for fk_court, fk_practice, last_number in court_cases:
    try:
        new_case_number = last_number + 1
        formatted_case_number = f"25{fk_court}{fk_practice}{new_case_number:05d}"
        
        if check_case_exists(formatted_case_number):
            cursor.execute("""
                INSERT INTO docketwatch.dbo.cases (case_number, fk_court, fk_practice, created_at)
                VALUES (?, ?, ?, GETDATE())
            """, (formatted_case_number, fk_court, fk_practice))
            
            cursor.execute("""
                UPDATE docketwatch.dbo.case_counter
                SET last_number = ?
                WHERE fk_court = ? AND fk_practice = ?
            """, (new_case_number, fk_court, fk_practice))
            conn.commit()
            logging.info(f"New case found: {formatted_case_number}")
            
            # Match celebrities
            match_celebrities(formatted_case_number)
        else:
            logging.info(f"No new case found for {formatted_case_number}")
    
    except Exception as e:
        logging.error(f"Error processing case {formatted_case_number}: {e}")
    
    time.sleep(1)

logging.info("✅ LA Court case scraping complete.")
