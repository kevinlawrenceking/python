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

# === DB Connection ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# === Helper: Fetch API Key from DB ===
def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row else None

# === Helper: Log errors to both console and log file ===
def log_error(msg):
    logging.error(msg)
    print("❌", msg)

# === GPT Prompt for Official URL ===
def fetch_official_url_from_gpt(court_name, state, county):
    prompt = (
        f"What is the official court website URL for the court named '{court_name}' "
        f"located in {county}, {state}? Respond only with the main homepage URL."
    )
    try:
        openai.api_key = get_chatgpt_key()
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that finds official U.S. court websites."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        url = response.choices[0].message["content"].strip()
        # Extract first URL-like string from the output
        match = re.search(r"https?://[^\s]+", url)
        return match.group(0) if match else None
    except Exception as e:
        log_error(f"ChatGPT API error: {e}")
        return None

# === Main Logic ===
def update_missing_court_urls():
    cursor.execute("""
        SELECT 
            c.court_code,
            c.court_name,
            c.state,
            ct.name as county
        FROM docketwatch.dbo.courts c
        INNER JOIN docketwatch.dbo.counties ct ON ct.id = c.fk_county
        WHERE c.court_url IS NULL
    """)
    records = cursor.fetchall()

    for row in records:
        court_code, court_name, state, county = row
        print(f"🔍 Looking up court URL for {court_code} – {court_name}...")

        url = fetch_official_url_from_gpt(court_name, state, county)
        if not url:
            log_error(f"No URL found for {court_code} – {court_name}")
            continue

        try:
            cursor.execute("""
                UPDATE docketwatch.dbo.courts
                SET court_url = ?
                WHERE court_code = ?
            """, url, court_code)
            conn.commit()
            logging.info(f"✅ Updated {court_code} with URL: {url}")
            print(f"✅ Updated {court_code} successfully.\n")
        except Exception as e:
            log_error(f"DB update failed for {court_code}: {e}")

        time.sleep(2)  # prevent hammering GPT

# === Run Script ===
if __name__ == "__main__":
    print("🚀 Starting GPT-based court URL updater...")
    update_missing_court_urls()
    print("✅ All done.")
