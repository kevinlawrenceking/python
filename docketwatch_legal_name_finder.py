import os
import pyodbc
import requests
import json
import time
from datetime import datetime

# === CONFIG ===
DSN = "Docketwatch"
script_filename = os.path.splitext(os.path.basename(__file__))[0]  # no .py
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"

# === Logging Setup ===
import logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === DB CONNECTION ===
conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("""
    SELECT TOP 1 r.id as fk_task_run 
    FROM docketwatch.dbo.task_runs r
    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
    WHERE s.filename = ? 
    ORDER BY r.id DESC
""", (script_filename,))
task_run = cursor.fetchone()
fk_task_run = task_run[0] if task_run else None

def log_message(log_type, message):
    logging.info(message)
    if fk_task_run:
        try:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.task_runs_log (fk_task_run, log_timestamp, log_type, description)
                OUTPUT INSERTED.id VALUES (?, GETDATE(), ?, ?)
            """, (fk_task_run, log_type, message))
            log_id = cursor.fetchone()[0]
            conn.commit()
            return log_id
        except Exception as e:
            print(f"Log Error: {e}")
            return None

log_message("INFO", "=== Legal Name Finder Script Started ===")

# === OpenAI API CONFIG ===
def get_api_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities")
    api_key = cursor.fetchone()
    return api_key[0] if api_key else None

HEADERS = {
    "Authorization": f"Bearer {get_api_key()}",
    "Content-Type": "application/json"
}
API_URL = "https://api.openai.com/v1/chat/completions"

# === Fetch Celebrities to Process ===
def get_celebrities():
    cursor.execute("""
        SELECT TOP 300 id, name
        FROM docketwatch.dbo.celebrities
        WHERE legal_name_found = 0 AND legal_alias_name_checked = 0
        ORDER BY priority_score DESC
    """)
    return cursor.fetchall()

# === Call OpenAI to Get Legal Name ===
def get_legal_name(celebrity_name):
    prompt = f"""
    I need to determine the current legal name of a celebrity for court case tracking. 
    Provide the legal name of {celebrity_name} ONLY if you are confident it is their current legal name.

    Guidelines for Accuracy: 
    - Provide the legal name only if it is publicly documented in a court case, government record, business registration, trademark filing, or a credible news report.
    - If only the birth name is available and there is no evidence of a legal name change, return the birth name.
    - If the person has legally changed their name, provide the most recent legally recognized name instead of the birth name.
    - If uncertain, return: "Legal name not confidently found."

    Response Format:
    {{
        "legal_name": "[Full Legal Name]",
        "source": "[Brief explanation of legal validity]"
    }}
    If no confident legal name is found, return:
    {{
        "legal_name": "Legal name not confidently found",
        "source": "No verified legal records available"
    }}
    """
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }
    response = requests.post(API_URL, headers=HEADERS, json=data)
    if response.status_code == 200:
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        log_message("ERROR", f"OpenAI API error for {celebrity_name}: {response.status_code}")
        return None

# === Update DB with Result ===
def update_database(celebrity_id, legal_name, source):
    MAX_LEGAL_GPT_NOTES = 100
    MAX_name = 500
    MAX_SOURCE = 500

    legal_name = legal_name[:MAX_name]
    source = source[:MAX_SOURCE]
    legal_gpt_notes = source[:MAX_LEGAL_GPT_NOTES]

    cursor.execute("""
        UPDATE docketwatch.dbo.celebrities
        SET legal_gpt_checked = 1, legal_gpt_notes = ?
        WHERE id = ?
    """, (legal_gpt_notes, celebrity_id))

    if legal_name and legal_name != "Legal name not confidently found":
        cursor.execute("""
            UPDATE docketwatch.dbo.celebrities
            SET legal_gpt_found = 1
            WHERE id = ?
        """, (celebrity_id,))
        cursor.execute("""
            SELECT id FROM docketwatch.dbo.celebrity_names
            WHERE name = ? AND fk_celebrity = ?
        """, (legal_name, celebrity_id))
        alias_exists = cursor.fetchone()
        if alias_exists:
            cursor.execute("""
                UPDATE docketwatch.dbo.celebrity_names
                SET type = 'Legal', source = ?
                WHERE fk_celebrity = ? AND name = ?
            """, (source, celebrity_id, legal_name))
        else:
            cursor.execute("""
                INSERT INTO docketwatch.dbo.celebrity_names (fk_celebrity, name, type, source)
                VALUES (?, ?, 'Legal', ?)
            """, (celebrity_id, legal_name, source))

    conn.commit()

# === Main Loop ===
def process_celebrities():
    celebrities = get_celebrities()
    for celeb_id, celeb_name in celebrities:
        print(f"Processing: {celeb_name}")
        log_message("INFO", f"Processing: {celeb_name}")
        try:
            result = get_legal_name(celeb_name)
            if result:
                response_data = json.loads(result)
                legal_name = response_data.get("legal_name", "")
                source = response_data.get("source", "")
                update_database(celeb_id, legal_name, source)
                log_message("INFO", f"Updated {celeb_name}: {legal_name}")
            else:
                update_database(celeb_id, "Legal name not confidently found", "No verified legal records available")
                log_message("WARNING", f"No valid legal name found for {celeb_name}")
        except Exception as e:
            log_message("ERROR", f"Error processing {celeb_name}: {e}")
        time.sleep(1.5)

if __name__ == "__main__":
    process_celebrities()
    log_message("INFO", "=== Legal Name Finder Script Completed ===")
    cursor.close()
    conn.close()
