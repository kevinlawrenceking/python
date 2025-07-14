import openai
import pyodbc
import logging
import os
import json
import re
import time

# === Logging Setup ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === Database Connection ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# === Helper: Fetch ChatGPT API Key from DB ===
def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row else None

# === Helper: Log + Print Errors ===
def log_error(msg):
    logging.error(msg)
    print("❌", msg)

# === Helper: Prompt GPT for Address Info ===
def fetch_address_from_gpt(court_name, state, county):
    prompt = (
        f"Given the federal court named '{court_name}' located in {county}, {state}, "
        "what is its most likely full street address, city, and ZIP code? "
        "Respond in JSON format using keys: address, city, zip."
    )
    try:
        openai.api_key = get_chatgpt_key()
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that returns JSON-formatted address data for U.S. federal courts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=400
        )
        content = response.choices[0].message["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            log_error("No JSON found in GPT response.")
            return None
        return json.loads(match.group(0))
    except Exception as e:
        log_error(f"ChatGPT API error: {e}")
        return None

# === Main Logic: Loop Through Courts ===
def update_missing_addresses():
    cursor.execute("""
        SELECT 
            c.court_code,
            c.court_name,
            c.state,
            ct.name as county
        FROM docketwatch.dbo.courts c
        INNER JOIN docketwatch.dbo.counties ct ON ct.id = c.fk_county
        WHERE c.address IS NULL OR c.city IS NULL OR c.zip IS NULL
    """)
    records = cursor.fetchall()

    for row in records:
        court_code, court_name, state, county = row
        print(f"🔍 Fetching address for {court_code} – {court_name}...")

        data = fetch_address_from_gpt(court_name, state, county)
        if not data:
            continue

        address = data.get("address")
        city = data.get("city")
        zip_code = data.get("zip")

        if not address or not city or not zip_code:
            log_error(f"Incomplete GPT result for {court_code}: {data}")
            continue

        try:
            cursor.execute("""
                UPDATE docketwatch.dbo.courts
                SET address = ?, city = ?, zip = ?
                WHERE court_code = ?
            """, address, city, zip_code, court_code)
            conn.commit()
            logging.info(f"✅ Updated {court_code}: {address}, {city}, {zip_code}")
            print(f"✅ Updated {court_code} successfully.\n")
        except Exception as e:
            log_error(f"DB update failed for {court_code}: {e}")
        
        time.sleep(2)  # Rate limit

# === Run Script ===
if __name__ == "__main__":
    print("🚀 Starting GPT-based court address updater...")
    update_missing_addresses()
    print("✅ All done.")
