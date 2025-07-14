import pyodbc
import requests
import time

# ✅ Database Connection
DB_CONNECTION = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.146.177.160;DATABASE=docketwatch;Trusted_Connection=yes;"

# ✅ Function to Fetch Celebrities Needing Birth Name Lookup
def get_unchecked_celebrities():
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()

    query = """
        SELECT l.id, c.id AS celebrity_id, c.name, l.external_id AS wikidata_id
        FROM docketwatch.dbo.celebrity_external_links l
        INNER JOIN docketwatch.dbo.celebrities c ON l.fk_celebrity = c.id
        WHERE l.source = 'Wikidata' 
          AND c.birth_alias_name_checked = 0 
        ORDER BY c.appearances DESC
    """

    cursor.execute(query)
    celebrities = cursor.fetchall()
    conn.close()

    return celebrities

# ✅ Function to Query Wikidata API for Birth Name
def get_birth_name(wikidata_id):
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&format=json&props=claims"
    response = requests.get(url).json()

    try:
        # Extract birth name (P1477) if available
        birth_name = response["entities"][wikidata_id]["claims"]["P1477"][0]["mainsnak"]["datavalue"]["value"]["text"]
        return birth_name.strip()
    except (KeyError, IndexError):
        return None  # No birth name found

# ✅ Function to Update Database with Birth Name
def update_birth_name(celebrity_id, birth_name):
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()

    # ✅ Insert Birth Name as Alias in `celebrity_names`
    if birth_name:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, type)
            SELECT ?, ?, 'Birth'
            WHERE NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.celebrity_names 
                WHERE fk_celebrity = ? AND name = ?
            )
        """, (celebrity_id, birth_name, celebrity_id, birth_name))

    # ✅ Mark `birth_alias_name_checked = 1` in `celebrities`
    cursor.execute("""
        UPDATE docketwatch.dbo.celebrities
        SET birth_alias_name_checked = 1
        WHERE id = ?
    """, (celebrity_id,))

    conn.commit()
    conn.close()

# ✅ Main Processing Loop
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
            update_birth_name(celeb_id, None)
            continue

        birth_name = get_birth_name(wikidata_id)

        if birth_name:
            print(f"Found birth name for {celeb_name}: {birth_name}")
        else:
            print(f"No birth name found for {celeb_name}.")

        # ✅ Update database
        update_birth_name(celeb_id, birth_name)
        
        # ✅ Wait a second to avoid API rate limits
        time.sleep(1)

# ✅ Run the script
if __name__ == "__main__":
    process_celebrities()
