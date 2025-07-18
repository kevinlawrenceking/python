import pyodbc
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import logging
import os
import concurrent.futures

# Setup Logging
# Use os.path.join for better path handling
try:
    server_path = r"\\10.146.176.84\general\docketwatch"
    log_dir = os.path.join(server_path, "python", "logs")
    os.makedirs(log_dir, exist_ok=True)
    LOG_FILE = os.path.join(log_dir, "docketwatch_celebrity_wikidata.log")
except OSError as e:
    # Fallback to local logging if network path is unavailable
    print(f"Warning: Could not access network log path: {e}")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    LOG_FILE = os.path.join(log_dir, "docketwatch_celebrity_wikidata.log")

# Configure logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Also log to console for visibility
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Database Configuration
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = None
cursor = None

def get_db_connection():
    """Get a fresh database connection"""
    try:
        connection = pyodbc.connect(DB_CONNECTION)
        connection.timeout = 30  # Set timeout to 30 seconds
        connection.autocommit = False  # Explicit transaction control
        return connection
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        raise

try:
    conn = get_db_connection()
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

# Function to fetch celebrities that need processing
def fetch_celebrities():
    query = """
    SELECT TOP 1000 id, name as celeb_name, wikidata_checked, birth_name_checked, legal_name_checked, alias_name_checked, wiki_processed
    FROM docketwatch.dbo.celebrities
    WHERE wiki_processed = 0 AND wikidata_checked = 0 AND wikidata_found = 0 and verified = 0
    ORDER BY appearances DESC
    """
    try:
        cursor.execute(query)
        celebrities = cursor.fetchall()
        logging.info(f"Fetched {len(celebrities)} celebrities from the database.")
        return celebrities
    except Exception as e:
        logging.error(f"Error fetching celebrities: {e}")
        raise

# Global variable to store celebrities (will be populated in main())
celebrities = []

# Wikidata API Endpoint
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# Create a session with retry logic for more robust API calls
def create_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "DocketWatch Celebrity Data Collection/1.0"})
    return session

# Create a global session to reuse
session = create_session()

def get_wikidata_id(celeb_name):
    """Get Wikidata entity ID for a celebrity name with improved matching"""
    try:
        # Parameters for entity search
        params = {
            "action": "wbsearchentities",
            "search": celeb_name,
            "language": "en",
            "format": "json",
            "limit": 5,  # Get multiple results to filter
            "type": "item"
        }
        
        response = session.get(WIKIDATA_API_URL, params=params).json()
        
        if "search" in response and response["search"]:
            # First pass - look for exact matches
            for item in response["search"]:
                if item.get("label", "").lower() == celeb_name.lower() or celeb_name.lower() in [alias.lower() for alias in item.get("aliases", [])]:
                    return item["id"]
            
            # If no exact match, check if "human" appears in description or look for common celebrity descriptors
            for item in response["search"]:
                description = item.get("description", "").lower()
                if any(term in description for term in ["actor", "actress", "singer", "performer", "celebrity", "musician", "athlete", "player", "human"]):
                    return item["id"]
            
            # If still no match, just return the first result
            return response["search"][0]["id"]
            
    except Exception as e:
        logging.error(f"Error fetching Wikidata ID for {celeb_name}: {e}")
    
    return None

def get_aliases_and_birth_name(wikidata_id):
    """Get both aliases and birth name in a single API call to reduce requests"""
    if not wikidata_id:
        return [], None
    
    try:
        params = {
            "action": "wbgetentities",
            "ids": wikidata_id,
            "props": "aliases|claims",
            "languages": "en",
            "format": "json"
        }
        
        response = session.get(WIKIDATA_API_URL, params=params).json()
        
        # Process data if available
        if "entities" in response and wikidata_id in response["entities"]:
            entity_data = response["entities"][wikidata_id]
            
            # Extract aliases
            aliases = []
            if "aliases" in entity_data and "en" in entity_data["aliases"]:
                aliases = [alias["value"].strip() for alias in entity_data["aliases"]["en"]]
            
            # Extract birth name (P1477 is the property for birth name)
            birth_name = None
            if "claims" in entity_data and "P1477" in entity_data["claims"]:
                try:
                    birth_name = entity_data["claims"]["P1477"][0]["mainsnak"]["datavalue"]["value"]["text"].strip()
                except (KeyError, IndexError):
                    pass
            
            return aliases, birth_name
            
    except Exception as e:
        logging.error(f"Error fetching data from Wikidata for ID {wikidata_id}: {e}")
    
    return [], None

# Legacy functions for backward compatibility
def get_aliases(wikidata_id):
    aliases, _ = get_aliases_and_birth_name(wikidata_id)
    return aliases

def get_birth_name(wikidata_id):
    _, birth_name = get_aliases_and_birth_name(wikidata_id)
    return birth_name

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
        SET alias_name_checked = 1, birth_name_checked = 1
        WHERE id = ?
    """, (celebrity_id,))
    conn.commit()

# Process celebrities in batches with configurable parameters
MAX_WORKERS = 5  # Parallel API requests
BATCH_SIZE = 20  # How many celebrities to process before committing
RATE_LIMIT_DELAY = 0.5  # Delay between API calls in seconds

def process_celebrity(celeb):
    """Process a single celebrity - can be run in parallel"""
    celeb_id, celeb_name, *_ = celeb
    
    try:
        wikidata_id = get_wikidata_id(celeb_name)
        results = {"id": celeb_id, "name": celeb_name, "wikidata_id": wikidata_id, 
                  "aliases": [], "birth_name": None, "success": False}
        
        if wikidata_id:
            # Get both aliases and birth name in one API call
            aliases, birth_name = get_aliases_and_birth_name(wikidata_id)
            results["aliases"] = aliases
            results["birth_name"] = birth_name
            results["success"] = True
            logging.info(f"Found Wikidata ID for {celeb_name}: {wikidata_id}")
            
            if aliases:
                logging.info(f"Found {len(aliases)} aliases for {celeb_name}")
            if birth_name:
                logging.info(f"Found birth name for {celeb_name}: {birth_name}")
                
        time.sleep(RATE_LIMIT_DELAY)  # Respect rate limits
        return results
    
    except Exception as e:
        logging.error(f"Error in worker processing {celeb_name}: {e}")
        return {"id": celeb_id, "name": celeb_name, "success": False, "error": str(e)}

# Main processing function with batching
def process_celebrity_batch():
    logging.info(f"Starting batch processing of {len(celebrities)} celebrities with {MAX_WORKERS} workers")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks and collect futures
        future_to_celeb = {executor.submit(process_celebrity, celeb): celeb for celeb in celebrities}
        
        # Helper function to ensure database connection is valid
        def ensure_connection():
            global conn, cursor
            try:
                # Test if connection is still valid
                cursor.execute("SELECT 1")
                return True
            except:
                logging.warning("Database connection lost. Reconnecting...")
                try:
                    if conn:
                        try:
                            conn.close()
                        except:
                            pass
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    logging.info("Database reconnection successful")
                    return True
                except Exception as e:
                    logging.error(f"Failed to reconnect to database: {e}")
                    return False

        # Process results as they complete
        for i, future in enumerate(concurrent.futures.as_completed(future_to_celeb)):
            celeb = future_to_celeb[future]
            celeb_id, celeb_name = celeb[0], celeb[1]
            
            try:
                # Get the result from the future
                result = future.result()
                results.append(result)
                
                # Ensure database connection is valid before proceeding
                if not ensure_connection():
                    logging.error("Cannot process celebrity without database connection")
                    continue
                
                # Update the database with the results
                if result["success"]:
                    if result["aliases"]:
                        insert_aliases(celeb_id, result["aliases"])
                    if result["birth_name"]:
                        insert_birth_name(celeb_id, result["birth_name"])
                    mark_aliases_checked(celeb_id)
                
                # Always mark as processed even if no data found
                cursor.execute("""
                    UPDATE docketwatch.dbo.celebrities
                    SET wikidata_checked = 1, wiki_processed = 1, wiki_update = GETDATE(),
                        wikidata_found = ?
                    WHERE id = ?
                """, (1 if result["wikidata_id"] else 0, celeb_id))
                
                # Commit in batches to avoid excessive commits
                if (i + 1) % BATCH_SIZE == 0:
                    conn.commit()
                    logging.info(f"Batch committed - processed {i+1}/{len(celebrities)} celebrities")
                
            except Exception as e:
                logging.error(f"Error processing results for {celeb_name}: {e}")
                try:
                    if ensure_connection():
                        cursor.execute("""
                            UPDATE docketwatch.dbo.celebrities 
                            SET wiki_processed = 1, wiki_update = GETDATE() 
                            WHERE id = ?
                        """, (celeb_id,))
                except Exception as db_error:
                    logging.error(f"Database error while marking celebrity as processed: {db_error}")
    
    # Final commit for any remaining records
    if ensure_connection():
        conn.commit()
    logging.info(f"Completed processing {len(results)} celebrities")
    return results

# Add summary statistics
def log_summary(results):
    if not results:
        logging.info("No results to summarize")
        return
        
    total = len(results)
    successful = sum(1 for r in results if r.get("success", False))
    with_aliases = sum(1 for r in results if r.get("aliases", []))
    with_birth_names = sum(1 for r in results if r.get("birth_name"))
    
    logging.info("=== Celebrity Wikidata Processing Summary ===")
    logging.info(f"Total processed: {total}")
    logging.info(f"Successfully found Wikidata IDs: {successful} ({successful/total*100:.1f}%)")
    logging.info(f"Found aliases: {with_aliases} ({with_aliases/total*100:.1f}%)")
    logging.info(f"Found birth names: {with_birth_names} ({with_birth_names/total*100:.1f}%)")
    logging.info("=== Processing complete ===")

# Main execution function
def main():
    global celebrities
    
    try:
        # Fetch celebrities to process
        celebrities = fetch_celebrities()
        
        if not celebrities:
            logging.info("No celebrities found to process. Exiting.")
            return
        
        # Execute the batch processing and log summary
        results = process_celebrity_batch()
        log_summary(results)
        
    except Exception as e:
        logging.error(f"Fatal error during processing: {e}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        if conn:
            try:
                cursor.close()
                conn.close()
                logging.info("Database connection closed")
            except Exception as e:
                logging.error(f"Error closing database connection: {e}")

# Run the script if executed directly
if __name__ == "__main__":
    main()
