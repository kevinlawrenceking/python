import pyodbc
import requests
import time

DB_CONNECTION = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.146.177.160;DATABASE=docketwatch;Trusted_Connection=yes;"

def get_unchecked_celebrities():
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    query = """
        SELECT l.id, c.id AS celebrity_id, c.name, l.external_id AS wikidata_id
        FROM docketwatch.dbo.celebrity_external_links l
        INNER JOIN docketwatch.dbo.celebrities c ON l.fk_celebrity = c.id
        WHERE l.source = 'Wikidata' AND c.legal_alias_name_checked = 0
        ORDER BY c.appearances DESC
    """
    
    cursor.execute(query)
    celebrities = cursor.fetchall()
    conn.close()
    
    return celebrities

def get_legal_name(wikidata_id):
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&format=json&props=claims"
    response = requests.get(url).json()
    
    try:
        legal_name = response["entities"][wikidata_id]["claims"]["P735"][0]["mainsnak"]["datavalue"]["value"]["text"]
        return legal_name.strip()
    except (KeyError, IndexError):
        return None  # No legal name found

def update_legal_name(celebrity_id, legal_name):
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    
    if legal_name:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, alias_type)
            SELECT ?, ?, 'Legal'
            WHERE NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.celebrity_names 
                WHERE fk_celebrity = ? AND name = ?
            )
        """, (celebrity_id, legal_name, celebrity_id, legal_name))

    cursor.execute("""
        UPDATE docketwatch.dbo.celebrities
        SET legal_alias_name_checked = 1
        WHERE id = ?
    """, (celebrity_id,))
    
    conn.commit()
    conn.close()

def process_celebrities():
    celebrities = get_unchecked_celebrities()

    if not celebrities:
        print("No unchecked celebrities found.")
        return

    for celeb in celebrities:
        celeb_id, celeb_name, wikidata_id = celeb[1], celeb[2], celeb[3]
        print(f"Checking {celeb_name} (Wikidata ID: {wikidata_id})...")

        legal_name = get_legal_name(wikidata_id)

        if legal_name:
            print(f"Found legal name for {celeb_name}: {legal_name}")
        else:
            print(f"No legal name found for {celeb_name}.")

        update_legal_name(celeb_id, legal_name)
        
        time.sleep(1)

if __name__ == "__main__":
    process_celebrities()