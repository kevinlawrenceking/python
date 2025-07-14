import pyodbc
import requests
import time
import logging
import os

# Setup Logging
log_dir = r"\\10.146.176.84\general\docketwatch\python\
logs"
os.makedirs(log_dir, exist_ok=True)
LOG_FILE = os.path.join(log_dir, "docketwatch_celebrity_wikidata.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Database Configuration

DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"

try:
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    logging.info("Connected to the database successfully.")
except Exception as e:
    logging.error(f"Error connecting to database: {e}")
    exit(1)

# Fetch Celebrities from DAMZ
def get_damz_celebrities():
    logging.info("Fetching celebrities from DAMZ database.")
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    query = """
        SELECT p.id, COUNT(*) AS appearances, 
               REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '') AS celebrity_name
        FROM damz.dbo.asset_metadata m
        INNER JOIN damz.dbo.asset a ON a.id = m.fk_asset
        INNER JOIN damz.dbo.picklist_celebrity p 
            ON p.name = REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '')
        WHERE a.created_at >= DATEADD(YEAR, -5, GETDATE())
          AND m.celebrity_in_photo IS NOT NULL 
          AND m.celebrity_in_photo <> '[]' 
          AND m.celebrity_in_photo <> '["Not Applicable"]'
		  and p.id not in (select id from docketwatch.dbo.celebrities)
        GROUP BY p.id, m.celebrity_in_photo
        HAVING COUNT(*) > 0
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    logging.info(f"Fetched {len(results)} celebrities from DAMZ.")
    return results

# Insert Celebrities into DocketWatch
def insert_celebrities():
    logging.info("Inserting new celebrities into DocketWatch database.")
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    inserted_count = 0
    
    celebrities = get_damz_celebrities()
    for celeb_id, celeb_appearances, celeb_name in celebrities:
        logging.info(f"Processing celebrity: {celeb_name} (ID: {celeb_id})")
        
        check_query = "SELECT 1 FROM docketwatch.dbo.celebrities WHERE id = ?"
        cursor.execute(check_query, (celeb_id,))
        
        if not cursor.fetchone():  # If no record found, insert
            insert_query = """
                INSERT INTO docketwatch.dbo.celebrities (id, name, appearances)
                VALUES (?, ?, ?)
            """
            cursor.execute(insert_query, (celeb_id, celeb_name, celeb_appearances))
            inserted_count += 1
            logging.info(f"Inserted: {celeb_name} (ID: {celeb_id})")
        else:
            logging.info(f"Skipped (Already Exists): {celeb_name} (ID: {celeb_id})")
    
    conn.commit()
    conn.close()
    logging.info(f"Insertion complete. Total new celebrities added: {inserted_count}")

# Run celebrity insert first
insert_celebrities()

# Query to fetch celebrities that need processing
query = """
SELECT TOP 1000 * 
FROM docketwatch.dbo.celebrities
WHERE wiki_processed = 0 AND wikidata_checked = 0 AND wikidata_found = 0
ORDER BY appearances DESC
"""
try:
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    cursor.execute(query)
    celebrities = cursor.fetchall()
    logging.info(f"Fetched {len(celebrities)} celebrities from the database.")
except Exception as e:
    logging.error(f"Error fetching celebrities: {e}")
    exit(1)

# Wikidata API Endpoint
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# (Remaining Wikidata Processing Code Remains Unchanged)
