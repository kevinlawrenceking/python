import requests
import pyodbc
import time

# ✅ Configure Database Connection
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=10.146.177.160;"
    "DATABASE=docketwatch;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()

# ✅ Query First 10 Unprocessed Celebrities
cursor.execute("""
    SELECT  id, name 
    FROM docketwatch.dbo.celebrities 
    WHERE wikidata_checked = 0
    ORDER BY NEWID()
""")  
celebrities = cursor.fetchall()

# ✅ Function to Search Wikidata
def search_wikidata(name):
    url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={name}&language=en&format=json"
    response = requests.get(url).json()
    
    if "search" in response and response["search"]:
        result = response["search"][0]
        return result.get("id"), result.get("label"), result.get("description")
    return None, None, None

# ✅ Process Each Celebrity
for celeb in celebrities:
    celeb_id = celeb[0]
    celeb_name = celeb[1]
    print(f"🔍 Searching Wikidata for: {celeb_name}")

    try:
        wikidata_id, label, description = search_wikidata(celeb_name)

        if wikidata_id:
            print(f"✅ Match Found: {label} ({wikidata_id}) - {description}")

            # ✅ Insert into `celebrity_external_links`
            cursor.execute("""
                INSERT INTO docketwatch.dbo.celebrity_external_links 
                (fk_celebrity, source, external_id, last_checked) 
                VALUES (?, ?, ?, GETDATE())
            """, (celeb_id, 'Wikidata', wikidata_id))

            # ✅ Mark as Processed
            cursor.execute("""
                UPDATE docketwatch.dbo.celebrities 
                SET wikidata_checked = 1
                WHERE id = ?
            """, (celeb_id,))
            conn.commit()

        else:
            print(f"❌ No Wikidata match found for {celeb_name}")

    except Exception as e:
        print(f"⚠️ Error processing {celeb_name}: {e}")

    time.sleep(1)  # Avoid rate limiting

# ✅ Close Connections
cursor.close()
conn.close()

print("🚀 Script Complete!")
