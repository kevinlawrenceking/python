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
#def get_damz_celebrities():
#    logging.info("Fetching celebrities from DAMZ database.")
#    conn = pyodbc.connect(DB_CONNECTION)
#    cursor = conn.cursor()
    
#    query = """
#        SELECT p.id, COUNT(*) AS appearances, 
#               REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '') AS celebrity_name
#        FROM damz.dbo.asset_metadata m
#        INNER JOIN damz.dbo.asset a ON a.id = m.fk_asset
#        INNER JOIN damz.dbo.picklist_celebrity p 
#            ON p.name = REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '')
#        WHERE a.created_at >= DATEADD(YEAR, -5, GETDATE())
#          AND m.celebrity_in_photo IS NOT NULL 
#          AND m.celebrity_in_photo <> '[]' 
#          AND m.celebrity_in_photo <> '["Not Applicable"]'
#          AND p.id not in (select id from docketwatch.dbo.celebrities)
#        GROUP BY p.id, m.celebrity_in_photo
#        HAVING COUNT(*) > 1
#    """
#    
#    cursor.execute(query)
#    results = cursor.fetchall()
#    conn.close()
#    logging.info(f"Fetched {len(results)} celebrities from DAMZ.")
#    return results

# Insert Celebrities into DocketWatch
#def insert_celebrities():
#    logging.info("Inserting new celebrities into DocketWatch database.")
#    conn = pyodbc.connect(DB_CONNECTION)
#    cursor = conn.cursor()
#    inserted_count = 0
    
#    celebrities = get_damz_celebrities()
#    for celeb_id, celeb_appearances, celeb_name in celebrities:
#        check_query = "SELECT 1 FROM docketwatch.dbo.celebrities WHERE id = ?"
#        cursor.execute(check_query, (celeb_id,))
        
#        if not cursor.fetchone():  # If no record found, insert
#            insert_query = """
#                INSERT INTO docketwatch.dbo.celebrities (id, name, appearances)
#                VALUES (?, ?, ?)
#            """
#            cursor.execute(insert_query, (celeb_id, celeb_name, celeb_appearances))
#            inserted_count += 1
#            logging.info(f"Inserted: {celeb_name} (ID: {celeb_id})")
#    
#    conn.commit()
#    conn.close()
#
#    if inserted_count > 0:
#        logging.info(f"Insertion complete. Total new celebrities added: {inserted_count}")


# Run celebrity insert first
#insert_celebrities()

# Query to fetch celebrities that need processing
query = """
SELECT TOP 1000 id, name as celeb_name, wikidata_checked, birth_alias_name_checked, legal_alias_name_checked, alias_name_checked, wiki_processed
FROM docketwatch.dbo.celebrities
WHERE wiki_processed = 0 AND wikidata_checked = 0 AND wikidata_found = 0 and verified = 0
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

def get_aliases(wikidata_id):
    url = f"{WIKIDATA_API_URL}?action=wbgetentities&ids={wikidata_id}&props=aliases&languages=en&format=json"
    response = requests.get(url).json()
    
    try:
        aliases = response["entities"][wikidata_id]["aliases"]["en"]
        return [alias["value"].strip() for alias in aliases]
    except (KeyError, IndexError):
        return []  # No aliases found

def get_birth_name(wikidata_id):
    url = f"{WIKIDATA_API_URL}?action=wbgetentities&ids={wikidata_id}&format=json&props=claims"
    response = requests.get(url).json()
    
    try:
        birth_name = response["entities"][wikidata_id]["claims"]["P1477"][0]["mainsnak"]["datavalue"]["value"]["text"]
        return birth_name.strip()
    except (KeyError, IndexError):
        return None  # No birth name found

def insert_aliases(celebrity_id, aliases):
    if not aliases:
        return  # No aliases to insert
    
    for alias in aliases:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, type)
                SELECT ?, ?, 'Alias'
                WHERE NOT EXISTS (
                    SELECT 1 FROM docketwatch.dbo.celebrity_names 
                    WHERE fk_celebrity = ? AND name = ?
                )
            """, (celebrity_id, alias, celebrity_id, alias))
        except pyodbc.Error as e:
            logging.error(f"Error inserting alias '{alias}': {e}")
    conn.commit()

def insert_birth_name(celebrity_id, birth_name):
    if not birth_name:
        return  # No birth name to insert
    
    try:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, type)
            SELECT ?, ?, 'Birth'
            WHERE NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.celebrity_names 
                WHERE fk_celebrity = ? AND name = ?
            )
        """, (celebrity_id, birth_name, celebrity_id, birth_name))
    except pyodbc.Error as e:
        logging.error(f"Error inserting birth name '{birth_name}': {e}")
    conn.commit()

def mark_aliases_checked(celebrity_id):
    cursor.execute("""
        UPDATE docketwatch.dbo.celebrities
        SET alias_name_checked = 1, birth_alias_name_checked = 1
        WHERE id = ?
    """, (celebrity_id,))
    conn.commit()

for celeb in celebrities:
    try:
        celeb_id, celeb_name, wikidata_checked, birth_alias_name_checked, legal_alias_name_checked, alias_name_checked, wiki_processed = celeb
        logging.info(f"Processing {celeb_name} ({celeb_id})")
        
        wikidata_id = get_wikidata_id(celeb_name)
        
        if wikidata_id:
            aliases = get_aliases(wikidata_id)
            birth_name = get_birth_name(wikidata_id)
            
            if aliases:
                logging.info(f"Found aliases for {celeb_name}: {', '.join(aliases)}")
                insert_aliases(celeb_id, aliases)
            if birth_name:
                logging.info(f"Found birth name for {celeb_name}: {birth_name}")
                insert_birth_name(celeb_id, birth_name)
            
            mark_aliases_checked(celeb_id)
        
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

logging.info("Celebrity Wikidata processing complete.")
