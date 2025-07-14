import openai
import pyodbc
import time
import os
import logging

# --- Setup Logging ---
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Database Config ---
DB_CONN = "DSN=Docketwatch;TrustServerCertificate=yes;"

# --- Fetch OpenAI API Key from DB ---
def get_openai_api_key(cursor):
    logging.info("Fetching OpenAI API key...")
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities WHERE id = 1")
    row = cursor.fetchone()
    if row:
        logging.info("API key fetched.")
    else:
        logging.error("API key not found.")
    return row[0] if row else None

# --- Fetch unmatched tracked cases ---
def fetch_unmatched_cases(cursor):
    logging.info("Fetching unmatched tracked cases...")
    query = """
    SELECT id, case_number, case_name
    FROM docketwatch.dbo.cases
    WHERE status = 'Tracked'
      AND id NOT IN (SELECT fk_case FROM docketwatch.dbo.case_celebrity_matches WHERE match_status <> 'Removed')
    """
    cursor.execute(query)
    results = cursor.fetchall()
    logging.info(f"Found {len(results)} unmatched cases.")
    return results

# --- Load all celebrity names (primary + aliases) ---
def load_celeb_names(cursor):
    logging.info("Loading celebrity names...")
    cursor.execute("""
        SELECT name FROM docketwatch.dbo.celebrity_names
        WHERE name IS NOT NULL AND LEN(name) >= 4
    """)
    names = set(row[0].lower() for row in cursor.fetchall())
    logging.info(f"Loaded {len(names)} celebrity names.")
    return names

def ask_chatgpt(case_name, case_number):
    prompt = f"""
You are assisting TMZ in identifying celebrities involved in legal cases.

CASE NAME: "{case_name}"
CASE NUMBER: {case_number}

Act as if you've searched Google News using the case name and number.
Based on patterns in media and public cases, which celebrity or celebrities are most likely involved?
Only name real celebrities — no lawyers, companies, or non-famous individuals. If unsure, say so.
"""

    logging.info("Sending prompt to ChatGPT...")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        logging.info(f"ChatGPT response: {content}")
        return content
    except Exception as e:
        logging.error(f"ChatGPT error: {e}")
        return ""


# --- Find known celebrity names in the response ---
def extract_celebs_from_response(response_text, celeb_names):
    found = []
    for name in celeb_names:
        if name.lower() in response_text.lower():
            found.append(name)
    logging.info(f"Matched celebrities: {found}")
    return found

# --- Insert celebrity match into the DB ---
def insert_celebrity_match(cursor, fk_case, celeb_name):
    logging.info(f"Inserting celebrity match: {celeb_name}")
    cursor.execute("""
        SELECT TOP 1 id FROM docketwatch.dbo.celebrities
        WHERE name = ? OR id IN (
            SELECT fk_celebrity FROM docketwatch.dbo.celebrity_names WHERE name = ?
        )
    """, celeb_name, celeb_name)
    row = cursor.fetchone()
    if not row:
        logging.warning(f"Celebrity not found in DB: {celeb_name}")
        return

    celeb_id = row[0]
    cursor.execute("""
        INSERT INTO docketwatch.dbo.case_celebrity_matches
        (fk_case, fk_celebrity, celebrity_name, probability_score, priority_score)
        VALUES (?, ?, ?, ?, NULL)
    """, fk_case, celeb_id, celeb_name, 0.9)
    logging.info(f"Match inserted: {celeb_name} → Case {fk_case}")

# --- Main Execution ---
def main():
    logging.info("Starting Celebrity Matcher script...")
    conn = pyodbc.connect(DB_CONN)
    cursor = conn.cursor()

    openai.api_key = get_openai_api_key(cursor)
    if not openai.api_key:
        logging.error("No OpenAI API key found. Exiting.")
        return

    unmatched_cases = fetch_unmatched_cases(cursor)
    celeb_names = load_celeb_names(cursor)

    for case in unmatched_cases:
        fk_case, case_number, case_name = case
        logging.info(f"Processing case: {case_name} [{case_number}]")

        gpt_response = ask_chatgpt(case_name, case_number)
        if not gpt_response:
            logging.warning("Empty GPT response. Skipping case.")
            continue

        # --- Update status_notes with GPT response ---
        try:
            truncated_note = gpt_response[:500]
            logging.info(f"Updating status_notes for case {fk_case}...")
            cursor.execute("""
                UPDATE docketwatch.dbo.cases
                SET status_notes = ?
                WHERE id = ?
            """, truncated_note, fk_case)
            conn.commit()
            logging.info(f"status_notes updated for case {fk_case}")
        except Exception as e:
            logging.error(f"Failed to update status_notes for case {fk_case}: {e}")

        # --- Insert any matched celebrities ---
        matched_names = extract_celebs_from_response(gpt_response, celeb_names)
        for celeb_name in matched_names:
            insert_celebrity_match(cursor, fk_case, celeb_name)
            conn.commit()

        time.sleep(2)

    cursor.close()
    conn.close()
    logging.info("Script finished successfully.")

if __name__ == "__main__":
    main()
