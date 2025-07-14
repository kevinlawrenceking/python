import pyodbc
import requests
import time

# **Database Connection**
DB_CONNECTION = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.146.177.160;DATABASE=docketwatch;Trusted_Connection=yes;"

# **Function to Fetch Celebrities Needing Alias Lookup**
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

# **Function to Query Wikidata API for Aliases**
def get_aliases_from_wikidata(wikidata_id):
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&format=json&props=aliases&languages=en"
    response = requests.get(url).json()

    aliases = []
    try:
        entity = response["entities"][wikidata_id]["aliases"]
        if "en" in entity:
            aliases = [alias["value"] for alias in entity["en"]]
    except (KeyError, IndexError):
        pass  # If nothing is found, return an empty list

    return aliases

# **Function to Insert Alias Names into `celebrity_names`**

def insert_alias(celebrity_id, name, alias_type):
    if not name:
        return  # Skip if no alias name found

    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM docketwatch.dbo.celebrity_names 
            WHERE fk_celebrity = ? AND name = ?
        )
        INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, [type])
        VALUES (?, ?, ?)
    """, (celebrity_id, name, celebrity_id, name, alias_type))
    
    conn.commit()
    conn.close()

# **Function to Update Check Flag in `celebrities`**
def mark_as_checked(celebrity_id):
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE docketwatch.dbo.celebrities
        SET alias_name_checked = 1
        WHERE id = ?
    """, (celebrity_id,))
    
    conn.commit()
    conn.close()

# **Main Processing Loop**
def process_celebrities():
    celebrities = get_unchecked_celebrities()

    if not celebrities:
        print("No unchecked celebrities found.")
        return

    for celeb in celebrities:
        record_id, celeb_id, celeb_name, wikidata_id = celeb
        print(f"Checking {celeb_name} (Wikidata ID: {wikidata_id})...")

        if not wikidata_id:
            print(f"No Wikidata ID found for {celeb_name}. Skipping...")
            mark_as_checked(celeb_id)
            continue

        # Fetch aliases from Wikidata
        aliases = get_aliases_from_wikidata(wikidata_id)

        if aliases:
            print(f"Found {len(aliases)} aliases for {celeb_name}: {', '.join(aliases)}")
            for alias in aliases:
                insert_alias(celeb_id, alias, "Alias")
        else:
            print(f"No aliases found for {celeb_name}.")

        # Update the celebrity as checked for aliases
        mark_as_checked(celeb_id)

        # Wait to avoid API rate limits
        time.sleep(1)

# **Run the script**
if __name__ == "__main__":
    process_celebrities()
