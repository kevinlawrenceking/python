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

# === Helper: Fetch ChatGPT Key ===
def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row else None

# === Error Logging Helper ===
def log_error(msg):
    logging.error(msg)
    print("❌", msg)

# === GPT Image URL Fetch ===
def fetch_courthouse_image_url(court_name, state, county, court_url=None):
    court_info = f"named '{court_name}' in {county} County, {state}"
    if court_url:
        court_info += f", website: {court_url}"
    prompt = (
        f"Find an official or news-credible image URL of the U.S. courthouse {court_info}. "
        "Respond with a direct URL to the image only. It should be an actual photo of the courthouse building, not a logo or icon. "
        "Do not include text, markdown, or formatting. Return only the image URL."
    )
    try:
        openai.api_key = get_chatgpt_key()
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that finds direct image URLs of U.S. courthouses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        content = response.choices[0].message["content"].strip()
        match = re.search(r"https?://\S+\.(jpg|jpeg|png|webp)", content, re.IGNORECASE)
        return match.group(0) if match else None
    except Exception as e:
        log_error(f"ChatGPT API error: {e}")
        return None

# === Main Logic ===
def update_missing_court_images():
    cursor.execute("""
        SELECT 
            c.court_code,
            c.court_name,
            c.state,
            ct.name as county,
            c.court_url
        FROM docketwatch.dbo.courts c
        INNER JOIN docketwatch.dbo.counties ct ON ct.id = c.fk_county
        WHERE c.image_location IS NULL
    """)
    records = cursor.fetchall()

    for row in records:
        court_code, court_name, state, county, court_url = row
        print(f"📸 Looking for image of {court_code} – {court_name}...")

        image_url = fetch_courthouse_image_url(court_name, state, county, court_url)
        if not image_url:
            log_error(f"No image found for {court_code}")
            continue

        try:
            cursor.execute("""
                UPDATE docketwatch.dbo.courts
                SET image_location = ?
                WHERE court_code = ?
            """, image_url, court_code)
            conn.commit()
            logging.info(f"✅ Image updated for {court_code}: {image_url}")
            print(f"✅ Updated {court_code} image URL.\n")
        except Exception as e:
            log_error(f"DB update failed for {court_code}: {e}")

        time.sleep(2)

# === Run Script ===
if __name__ == "__main__":
    print("🚀 Starting courthouse image updater...")
    update_missing_court_images()
    print("✅ All done.")
