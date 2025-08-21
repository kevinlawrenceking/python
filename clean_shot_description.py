import pyodbc
import google.generativeai as genai
import re
import time

# --- CONFIG ---
BATCH_LIMIT = 5000
GEMINI_MODEL = "gemini-1.5-flash"
TEMPERATURE = 0.2  # low for rule-following
MAX_TOKENS = 200   # one-line output
SLEEP_SECONDS = 0.5
DEBUG_MODE = False

# --- Prompt Setup ---
PROMPT_RULES_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_shotdesc.txt"

def load_prompt_rules():
    with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
        return f.read()

# --- Gemini Key Retrieval ---
def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

# --- Optional local cleanup in case the model misses something ---
CREDIT_PATTERNS = [
    r"photo by [^,]+(,|\.)?.*$",
    r"via getty images.*$",
    r"getty images.*$",
    r"ap photo.*$",
    r"reuters.*$",
]
EDITOR_PATTERNS = [
    r"editor'?s note.*?$",
    r"unspecified(?:,|\s|-).*?",
    r"image has been retouched.*?$",
]

def post_clean(text):
    if not text:
        return text

    s = text.strip()

    # kill credits and editor notes if any slipped through
    for pat in CREDIT_PATTERNS + EDITOR_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)

    # collapse spaces, commas
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = s.strip(" ,")

    # max ~15 words as a hard guard
    words = s.split()
    if len(words) > 15:
        s = " ".join(words[:15])

    return s

# --- Prompt Builder ---
def build_prompt(rules, headline_v5, shot_description):
    # Headline gives context for names/event normalization. Keep it brief.
    headline_v5 = headline_v5 or ""
    shot_description = shot_description or ""

    return f"""{rules}

INPUT
Headline: {headline_v5}
Raw_Shot_Description: {shot_description}
"""

# --- Gemini Call ---
def clean_shot_description(prompt, gemini_key):
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": MAX_TOKENS
            }
        )

        text = (response.text or "").strip()
        if DEBUG_MODE:
            print(f"[DEBUG] Gemini raw: {text}")

        # Use first non-empty line only
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return None

        cleaned = lines[0]
        # defensive strip of quotes and trailing punctuation
        cleaned = cleaned.strip(" '\"")
        cleaned = post_clean(cleaned)

        return cleaned if cleaned else None

    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        return None

# --- Main Logic ---
def main():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    rules = load_prompt_rules()
    if DEBUG_MODE:
        print(f"[DEBUG] Loaded prompt rules: {len(rules)} chars")
        print(rules[:400])

    gemini_key = get_gemini_key(cursor)
    if not gemini_key:
        print("ERROR: Gemini API key not found.")
        return

    # Confirm target column exists
    try:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'damz_test' AND TABLE_SCHEMA = 'dbo'
              AND COLUMN_NAME IN ('headline_v5','shot_description','shot_description_new')
        """)
        cols = {row[0] for row in cursor.fetchall()}
        if 'headline_v5' not in cols:
            print("WARNING: Column 'headline_v5' not found.")
        if 'shot_description_new' not in cols:
            print("WARNING: Column 'shot_description_new' not found.")
    except Exception as e:
        print(f"[DEBUG] Column check failed: {e}")

    # Pull rows where headline_v5 is not null
    cursor.execute(f"""
        SELECT TOP {1 if DEBUG_MODE else BATCH_LIMIT}
               fk_asset,
               headline_v5,
               shot_description
        FROM docketwatch.dbo.damz_test
        WHERE headline_v5 IS NOT NULL
        ORDER BY fk_asset
    """)
    rows = cursor.fetchall()

    if DEBUG_MODE:
        print("[DEBUG MODE] Limiting to 1 record")

    print(f"Found {len(rows)} records to process")
    processed, skipped = 0, 0

    for fk_asset, headline_v5, shot_description in rows:
        print(f"\nAsset: {fk_asset}")
        if DEBUG_MODE:
            print(f"[DEBUG] headline_v5: {str(headline_v5)[:140]}")
            print(f"[DEBUG] shot_description: {str(shot_description)[:140]}")

        prompt = build_prompt(rules, headline_v5, shot_description)
        cleaned = clean_shot_description(prompt, gemini_key)

        if cleaned:
            # Show current before update
            cursor.execute("""
                SELECT shot_description_new
                FROM docketwatch.dbo.damz_test
                WHERE fk_asset = ?
            """, (fk_asset,))
            before = cursor.fetchone()
            if DEBUG_MODE:
                print(f"[DEBUG] Before: {before[0] if before else 'NULL'}")

            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET shot_description_new = ?
                WHERE fk_asset = ?
            """, (cleaned, fk_asset))
            conn.commit()

            # Verify
            cursor.execute("""
                SELECT shot_description_new
                FROM docketwatch.dbo.damz_test
                WHERE fk_asset = ?
            """, (fk_asset,))
            after = cursor.fetchone()
            print(f"OK: {fk_asset} -> {after[0] if after else cleaned}")
            processed += 1
        else:
            print(f"SKIP: {fk_asset} (no cleaned output)")
            skipped += 1

        time.sleep(SLEEP_SECONDS)

    print("\n=== BATCH COMPLETE ===")
    print(f"Processed: {processed}")
    print(f"Skipped:   {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
