# celebrity_sync.py - Full celebrity synchronization process
import pyodbc
import requests
import time
import logging
import os

# Setup Logging
log_dir = r"\\10.146.176.84\general\docketwatch\python\logs"
os.makedirs(log_dir, exist_ok=True)
LOG_FILE = os.path.join(log_dir, "celebrity_wikidata.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Database Connection
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
try:
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    logging.info("Connected to the database successfully.")
except Exception as e:
    logging.error(f"Error connecting to database: {e}")
    exit(1)

def insert_new_celebrities():
    """Find and insert new celebrities from DAMZ into DocketWatch."""
    query = """
    SELECT p.id, COUNT(*) as appearances,
           REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '') AS celebrity_name
    FROM [damz].[dbo].[asset_metadata] m
    INNER JOIN [damz].[dbo].[asset] a ON a.id = m.fk_asset
    INNER JOIN [damz].[dbo].[picklist_celebrity] p ON p.name = REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '')
    WHERE a.created_at >= DATEADD(YEAR, -5, GETDATE())  
      AND m.celebrity_in_photo IS NOT NULL 
      AND m.celebrity_in_photo <> '[]' 
      AND m.celebrity_in_photo <> '["Not Applicable"]'
    GROUP BY p.id, m.celebrity_in_photo
    HAVING COUNT(*) > 1 AND p.id NOT IN (
        SELECT id FROM [docketwatch].[dbo].[celebrities]
    )
    """
    cursor.execute(query)
    new_celebrities = cursor.fetchall()
    
    for celeb_id, appearances, celeb_name in new_celebrities:
        cursor.execute("""
        INSERT INTO docketwatch.dbo.celebrities (id, name, appearances)
        SELECT ?, ?, ? WHERE NOT EXISTS (
            SELECT 1 FROM docketwatch.dbo.celebrities WHERE id = ?
        )
        """, (celeb_id, celeb_name, appearances, celeb_id))
        conn.commit()
    logging.info(f"Inserted {len(new_celebrities)} new celebrities into DocketWatch.")

# Run insert first
insert_new_celebrities()

# Query to fetch celebrities that need processing
query = """
SELECT TOP 1000 id, name as celeb_name, wikidata_checked, birth_alias_name_checked, legal_alias_name_checked, alias_name_checked, wiki_processed
FROM docketwatch.dbo.celebrities
WHERE wiki_processed = 0 AND wikidata_checked = 0 AND wikidata_found = 0
ORDER BY appearances DESC
"""
try:
    cursor.execute(query)
    celebrities = cursor.fetchall()
    logging.info(f"Fetched {len(celebrities)} celebrities from the database.")
except Exception as e:
    logging.error(f"Error fetching celebrities: {e}")
    exit(1)

# Wikidata API Endpoint
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

def get_wikidata_id(celeb_name):
    try:
        params = {
            "action": "wbsearchentities",
            "search": celeb_name,
            "language": "en",
            "format": "json"
        }
        response = requests.get(WIKIDATA_API_URL, params=params).json()
        
        if "search" in response and response["search"]:
            return response["search"][0]["id"]
    except Exception as e:
        logging.error(f"Error fetching Wikidata ID for {celeb_name}: {e}")
    return None

for celeb in celebrities:
    try:
        celeb_id, celeb_name, wikidata_checked, birth_alias_name_checked, legal_alias_name_checked, alias_name_checked, wiki_processed = celeb
        logging.info(f"Processing {celeb_name} ({celeb_id})")
        
        wikidata_id = get_wikidata_id(celeb_name)
        
        cursor.execute("""
            UPDATE docketwatch.dbo.celebrities
            SET wikidata_checked = 1, wiki_processed = 1, wiki_update = GETDATE()
            WHERE id = ?
        """, (celeb_id,))
        conn.commit()
        
        logging.info(f"Processed {celeb_name}: Wikidata ID {wikidata_id}")
    except Exception as e:
        logging.error(f"Error processing {celeb_name}: {e}")
        cursor.execute("UPDATE docketwatch.dbo.celebrities SET wiki_processed = 1, wiki_update = GETDATE() WHERE id = ?", celeb_id)
        conn.commit()
    
    time.sleep(1)

logging.info(" Celebrity Wikidata processing complete.")
