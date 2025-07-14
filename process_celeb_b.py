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

# Query to fetch celebrities that need processing
query = """
SELECT top 1000 id, name as celeb_name, wikidata_checked, birth_alias_name_checked, legal_alias_name_checked, alias_name_checked, wiki_processed
FROM docketwatch.dbo.celebrities
WHERE wiki_processed = 0 and wikidata_checked = 0 and wikidata_found = 0
ORDER BY appearances
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

def get_wikidata_details(wikidata_id):
    try:
        params = {
            "action": "wbgetentities",
            "ids": wikidata_id,
            "languages": "en",
            "format": "json"
        }
        response = requests.get(WIKIDATA_API_URL, params=params).json()
        
        entity = response.get("entities", {}).get(wikidata_id, {}).get("claims", {})
        
        birth_name = entity.get("P1477", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("text")
        legal_name = entity.get("P735", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("text")
        aliases = [alias["value"] for alias in response["entities"].get(wikidata_id, {}).get("aliases", {}).get("en", [])]
        
        return birth_name, legal_name, aliases
    except Exception as e:
        logging.error(f"Error fetching details for Wikidata ID {wikidata_id}: {e}")
        return None, None, []

for celeb in celebrities:
    try:
        celeb_id, celeb_name, wikidata_checked, birth_alias_name_checked, legal_alias_name_checked, alias_name_checked, wiki_processed = celeb
        logging.info(f"Processing {celeb_name} ({celeb_id})")
        
        wikidata_id = get_wikidata_id(celeb_name)
        birth_name, legal_name, aliases = (None, None, [])
        
        if wikidata_id:
            birth_name, legal_name, aliases = get_wikidata_details(wikidata_id)
            cursor.execute("""
                INSERT INTO docketwatch.dbo.celebrity_external_links (fk_celebrity, source, external_id, last_checked)
                SELECT ?, 'Wikidata', ?, GETDATE()
                WHERE NOT EXISTS (
                    SELECT 1 FROM docketwatch.dbo.celebrity_external_links
                    WHERE fk_celebrity = ? AND external_id = ?
                )
            """, (celeb_id, wikidata_id, celeb_id, wikidata_id))
            conn.commit()
        
        cursor.execute("""
            UPDATE docketwatch.dbo.celebrities
            SET wikidata_checked = 1, birth_alias_name_checked = 1, legal_alias_name_checked = 1, alias_name_checked = 1,
                wikidata_found = ?, birth_name_found = ?, legal_name_found = ?, name_found = ?,
                wiki_processed = 1, wiki_update = GETDATE()
            WHERE id = ?
        """, (1 if wikidata_id else 0, 1 if birth_name else 0, 1 if legal_name else 0, 1 if aliases else 0, celeb_id))
        conn.commit()
        
        for name, alias_type in [(birth_name, 'Birth'), (legal_name, 'Legal')] + [(alias, 'Alias') for alias in aliases]:
            if name:
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, type)
                    SELECT ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM docketwatch.dbo.celebrity_names WHERE fk_celebrity = ? AND name = ?
                    )
                """, (celeb_id, name, alias_type, celeb_id, name))
                conn.commit()
        
        logging.info(f"Processed {celeb_name}: Wikidata ID {wikidata_id}, Birth Name: {birth_name}, Legal Name: {legal_name}, Aliases: {aliases}")
    except Exception as e:
        logging.error(f"Error processing {celeb_name}: {e}")
        cursor.execute("UPDATE docketwatch.dbo.celebrities SET wiki_processed = 1, wiki_update = GETDATE() WHERE id = ?", celeb_id)
        conn.commit()
    
    time.sleep(1)

logging.info("✅ Celebrity Wikidata processing complete.")
