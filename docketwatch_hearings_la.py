import requests
import pyodbc
import logging
import os
from datetime import datetime, timedelta
from case_processing import process_case  # Process parties & names
from celebrity_matches import check_celebrity_matches  # Check celebrity matches

# Setup Logging
log_dir = r"\\10.146.176.84\general\docketwatch\python\
logs"
os.makedirs(log_dir, exist_ok=True)
LOG_FILE = os.path.join(log_dir, "docketwatch_hearings_la.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# **Database Connection**
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = pyodbc.connect(DB_CONNECTION)
cursor = conn.cursor()
logging.info("Connected to the database successfully.")

# **Find the next 10 departments to process (excluding already processed ones)**
query = """
SELECT TOP 10  
    c.court_id, 
    c.court_code, 
    d.id AS department_id,
    MIN(h.id) AS oldest_hearing
FROM [dbo].[courts] c
INNER JOIN [dbo].[departments] d ON d.fk_court_id = c.court_id
left JOIN [docketwatch].[dbo].[hearings] h ON h.fk_court_id = c.court_id
GROUP BY 
    c.court_id, 
    c.court_code, 
    d.id
ORDER BY 
    MIN(h.id)
"""
cursor.execute(query)
departments = cursor.fetchall()

if not departments:
    logging.info("All departments have been processed. No new imports needed.")
    cursor.close()
    conn.close()
    exit()

DATE_FROM = datetime.today().strftime("%m-%d-%Y")
DATE_TO = (datetime.today() + timedelta(days=60)).strftime("%m-%d-%Y")

for COURT_ID, COURT_CODE, DEPARTMENT_ID in departments:
    API_URL = f"https://media.lacourt.org/lascmediaproxy/api/AzureApi/CriminalCalendarSearchByLocationNew/CR/{COURT_ID}/{DEPARTMENT_ID}/{DATE_FROM}/{DATE_TO}"
    
    logging.info(f"Processing hearings for Court ID: {COURT_ID}, Department ID: {DEPARTMENT_ID}")
    logging.info(f"Fetching data from: {API_URL}")
    
    response = requests.get(API_URL)
    
    if response.status_code == 200:
        data = response.json()
        
        if data["isSuccess"]:
            hearings = data["resultList"]
            logging.info(f"Received {len(hearings)} hearings for Dept {DEPARTMENT_ID}.")
            
            for hearing in hearings:
                case_number = hearing["caseNumber"][:50]
                case_name = " ".join(hearing["caseTitle"].splitlines())[:255]
                case_type = hearing["caseType"][:400]
                case_status = hearing.get("caseStatus", "Unknown")[:100]
                hearing_type = hearing["hearingType"]
                hearing_datetime = hearing["hearingDateTime"]
                
                cursor.execute("SELECT ID FROM docketwatch.dbo.cases WHERE case_number = ?", (case_number,))
                case_result = cursor.fetchone()
                fk_case = case_result[0] if case_result else None
                
                if fk_case is None:
                    insert_case_query = """
                    INSERT INTO docketwatch.dbo.cases (case_number, case_name, case_type, case_status, created_at, last_updated)
                    VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
                    """
                    cursor.execute(insert_case_query, (case_number, case_name, case_type, case_status))
                    conn.commit()
                    
                    cursor.execute("SELECT ID FROM docketwatch.dbo.cases WHERE case_number = ?", (case_number,))
                    fk_case = cursor.fetchone()[0]
                    
                    process_case(fk_case, case_number, case_name, "LAC")
                
                cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.hearings WHERE fk_case = ? AND hearing_datetime = ?", (fk_case, hearing_datetime))
                count = cursor.fetchone()[0]
                
                if count == 0:
                    insert_query = """
                    INSERT INTO docketwatch.dbo.hearings (fk_case, hearing_type, hearing_datetime, created_at)
                    VALUES (?, ?, ?, ?)
                    """
                    cursor.execute(insert_query, (fk_case, hearing_type, hearing_datetime, datetime.now()))
                    logging.info(f"Inserted hearing: {hearing_type} on {hearing_datetime}")
                else:
                    logging.info(f"Skipping existing hearing: {hearing_type} on {hearing_datetime}")
            
            conn.commit()
            logging.info(f"Hearings for Department {DEPARTMENT_ID} updated successfully!")
            
            cursor.execute("""
            INSERT INTO docketwatch.dbo.hearingImportLog (court_id, department_id, date_imported, timestamp)
            VALUES (?, ?, ?, GETDATE())
            """, (COURT_ID, DEPARTMENT_ID, DATE_FROM))
            conn.commit()
            logging.info(f"Logged hearing import for Dept {DEPARTMENT_ID}.")
        else:
            logging.error(f"API Response Error: {data['errorMessage']}")
    else:
        logging.error(f"API Request Failed! Status Code: {response.status_code}")

check_celebrity_matches()
logging.info("Checked for celebrity matches.")

cursor.close()
conn.close()
logging.info("Script Completed Successfully!")