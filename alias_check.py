import pyodbc
import requests
import time

# Database Connection String
DB_CONNECTION = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.146.177.160;DATABASE=docketwatch;Trusted_Connection=yes;"

# Fetch celebrities that need alias checks
def get_unchecked_celebrities():
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    query = """
        SELECT l.id, c.id AS celebrity_id, c.name, l.external_id AS wikidata_id
        FROM docketwatch.dbo.celebrity_external_links l
        INNER JOIN docketwatch.dbo.celebrities c ON l.fk_celebrity = c.id
        WHERE l.source = 'Wikidata' AND c.alias_name_checked = 0
        ORDER BY c.appearances DESC
    """
    
    cursor.execute(query)
    celebrities = cursor.fetchall()
    conn.close()
    
    return celebrities

# Query Wikidata API for Aliases
def get_aliases(wikidata_id):
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&props=aliases&languages=en&format=json"
    response = requests.get(url).json()
    
    try:
        aliases = response["entities"][wikidata_id]["aliases"]["en"]
        return [alias["value"].strip() for alias in aliases]
    except (KeyError, IndexError):
        return []  # No aliases found

# Insert aliases into the database
def insert_aliases(celebrity_id, aliases):
    if not aliases:
        return  # No aliases to insert

    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()

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
            print(f"⚠️ Error inserting alias '{alias}': {e}")

    conn.commit()
    conn.close()

# Mark the celebrity as checked for aliases
def mark_aliases_checked(celebrity_id):
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE docketwatch.dbo.celebrities
        SET alias_name_checked = 1
        WHERE id = ?
    """, (celebrity_id,))
    
    conn.commit()
    conn.close()

# Processing loop
def process_celebrities():
    celebrities = get_unchecked_celebrities()

    if not celebrities:
        print("No unchecked celebrities found.")
        return

    for celeb in celebrities:
        celeb_id, celeb_name, wikidata_id = celeb[1], celeb[2], celeb[3]
        print(f"Checking {celeb_name} (Wikidata ID: {wikidata_id})...")

        aliases = get_aliases(wikidata_id)

        if aliases:
            print(f"Found aliases for {celeb_name}: {', '.join(aliases)}")
            insert_aliases(celeb_id, aliases)
        else:
            print(f"No aliases found for {celeb_name}.")

        mark_aliases_checked(celeb_id)
        
        time.sleep(1)  # Avoid API rate limits

# Run the script
if __name__ == "__main__":
    process_celebrities()
