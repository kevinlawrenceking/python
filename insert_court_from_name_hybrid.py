import openai
import pyodbc
import json
import random
import string
import sys
import re

# Database connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# Get court name from command-line argument
if len(sys.argv) < 2:
    print("Usage: python insert_court_from_name_hybrid.py <court name>")
    sys.exit(1)

court_name_input = sys.argv[1]

# Helper to generate 5-character court_code
def generate_court_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

# Get API key from database
def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else None

openai.api_key = get_chatgpt_key()

# Step 1: Ask GPT to find the official court website
prompt = f"""
What is the official homepage URL of the U.S. court called: "{court_name_input}"?
Just return the full URL only if known. You can suggest it even if you're unsure.
"""

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0
)

raw_url_response = response.choices[0].message.content.strip()
url_match = re.search(r'https?://[^\s)]+', raw_url_response)

if not url_match:
    print("ERROR: No valid URL found in ChatGPT response.")
    print("Response was:", raw_url_response)
    sys.exit(1)

court_url = url_match.group(0)

# Step 2: Ask GPT for court details from that URL
prompt = f"""
Given the court website: {court_url}

Return the following court fields:
- court_name
- address
- city
- state (2-letter)
- zip
- image_url
Return as JSON.
"""

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)

content = response.choices[0].message.content.strip()

try:
    court_data = json.loads(content)
except json.JSONDecodeError:
    print("ERROR: ChatGPT did not return valid JSON.")
    print("Response was:\n", content)
    sys.exit(1)

# Extract fields
court_name = court_data.get("court_name")
address = court_data.get("address")
city = court_data.get("city")
state = court_data.get("state")
zip_code = court_data.get("zip")
image_location = court_data.get("image_location")

# Keep original URL unless GPT returned a valid one
court_url_from_json = court_data.get("court_url")
if court_url_from_json and court_url_from_json.startswith("http"):
    court_url = court_url_from_json

# Step 2.5: Check if court already exists
cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_url = ?", court_url)
row = cursor.fetchone()
if row:
    print(row[0])
    cursor.close()
    conn.close()
    sys.exit(0)

# Step 3: Lookup or Insert County
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

# Step 4: Insert into courts
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

# ✅ Final output: court_code only
print(court_code)

cursor.close()
conn.close()
