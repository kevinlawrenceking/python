import pyodbc
import json
import random
import string
import sys
import requests
import openai

# Database connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# Get court name from command-line argument
if len(sys.argv) < 2:
    print("Usage: python insert_court_from_name_wikidata.py <court name>")
    sys.exit(1)

input_name = sys.argv[1]

# --- Helper functions ---

def generate_court_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else None

def query_wikidata_for_url(court_name):
    endpoint = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/sparql-results+json"}
    query = f"""
    SELECT ?item ?itemLabel ?officialWebsite WHERE {{
      ?item ?label "{court_name}"@en.
      ?item wdt:P856 ?officialWebsite.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
    }}
    LIMIT 1
    """
    response = requests.get(endpoint, params={'query': query, 'format': 'json'}, headers=headers)
    data = response.json()
    try:
        return data['results']['bindings'][0]['officialWebsite']['value']
    except (IndexError, KeyError):
        return None

def get_court_details_from_url(court_url):
    openai.api_key = get_chatgpt_key()
    prompt = f"""
    Given the court website: {court_url}

    Return the following court fields in JSON:
    {{
      "court_name": "...",
      "address": "...",
      "city": "...",
      "state": "...",
      "zip": "...",
      "image_location": "...",
      "court_url": "{court_url}"
    }}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("ERROR: ChatGPT did not return valid JSON.")
        print("Response was:\n", content)
        sys.exit(1)

# --- Step 1: Check if court already exists ---
cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_name LIKE ?", f"%{input_name}%")
existing = cursor.fetchone()
if existing:
    print(existing[0])
    cursor.close()
    conn.close()
    sys.exit(0)

# --- Step 2: Use Wikidata to get court URL ---
court_url = query_wikidata_for_url(input_name)
if not court_url:
    print("ERROR: Court URL not found in Wikidata.")
    sys.exit(1)

# --- Step 3: Use GPT to get full court details ---
court_data = get_court_details_from_url(court_url)

# --- Step 4: Extract and sanitize fields ---
court_name = court_data.get("court_name")
address = court_data.get("address")
city = court_data.get("city")
state = court_data.get("state")
zip_code = court_data.get("zip")
image_location = court_data.get("image_location")

# --- Step 5: Lookup or insert county ---
cursor.execute("SELECT id FROM docketwatch.dbo.counties WHERE name = ?", city)
row = cursor.fetchone()

if row:
    county_id = row[0]
else:
    code = city[:5].upper()
    cursor.execute("""
        INSERT INTO docketwatch.dbo.counties (name, code, state_code)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?)
    """, (city, code, state))
    county_id = cursor.fetchone()[0]
    conn.commit()

# --- Step 6: Insert court record ---
court_code = generate_court_code()
cursor.execute("""
    INSERT INTO docketwatch.dbo.courts (
        court_code, court_name, address, city, state, zip, image_location,
        fk_county, court_id, court_url, last_scraped
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL)
""", (
    court_code, court_name, address, city, state, zip_code,
    image_location, county_id, court_url
))
conn.commit()

# --- Final Output ---
print(court_code)

cursor.close()
conn.close()
