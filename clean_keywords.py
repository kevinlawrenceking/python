import pyodbc
import google.generativeai as genai
import json
import re
import time

# --- CONFIG ---
BATCH_LIMIT = 5000
GEMINI_MODEL = "gemini-1.5-flash"
TEMPERATURE = 0.2  # low for rule-following
MAX_TOKENS = 300   # for keyword arrays
SLEEP_SECONDS = 0.5
DEBUG_MODE = False

# --- Prompt Setup ---
PROMPT_RULES_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_keywords.txt"

def load_prompt_rules():
    with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
        return f.read()

# --- Gemini Key Retrieval ---
def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

# --- Optional local cleanup for keywords ---
VAGUE_TERMS = {
    "body", "torso", "booze", "object", "thing", "nice", "cool", 
    "stuff", "item", "piece", "element", "part", "area", "section"
}

def post_clean_keywords(keywords_array):
    if not keywords_array:
        return []
    
    cleaned = []
    seen = set()
    
    for keyword in keywords_array:
        if not keyword or not isinstance(keyword, str):
            continue
            
        # Basic cleanup
        kw = keyword.strip().lower()
        
        # Skip vague terms
        if kw in VAGUE_TERMS:
            continue
            
        # Skip if too short or too long
        if len(kw) < 2 or len(kw) > 50:
            continue
            
        # Deduplicate (case insensitive)
        if kw not in seen:
            seen.add(kw)
            cleaned.append(keyword.strip())
    
    # Limit to 15 keywords max
    return cleaned[:15]

# --- Prompt Builder ---
def build_prompt(rules, keywords_raw):
    # Parse keywords from string if needed
    if isinstance(keywords_raw, str):
        # Try to parse as JSON first
        try:
            keywords_list = json.loads(keywords_raw)
        except:
            # Fall back to splitting by common delimiters
            keywords_list = re.split(r'[,;|]', keywords_raw)
    else:
        keywords_list = keywords_raw or []
    
    # Clean up the list
    keywords_list = [kw.strip() for kw in keywords_list if kw and kw.strip()]
    
    return f"""{rules}

INPUT
{json.dumps(keywords_list)}
"""

# --- Gemini Call ---
def clean_keywords(prompt, gemini_key):
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

        # Try to parse as JSON
        try:
            # Find JSON array in response
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                keywords_array = json.loads(json_match.group())
                if isinstance(keywords_array, list):
                    cleaned = post_clean_keywords(keywords_array)
                    return json.dumps(cleaned) if cleaned else None
        except Exception as e:
            if DEBUG_MODE:
                print(f"[DEBUG] JSON parse failed: {e}")
        
        return None

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
              AND COLUMN_NAME IN ('shot_description_new','keywords','keywords_new')
        """)
        cols = {row[0] for row in cursor.fetchall()}
        if 'shot_description_new' not in cols:
            print("WARNING: Column 'shot_description_new' not found.")
        if 'keywords_new' not in cols:
            print("WARNING: Column 'keywords_new' not found.")
    except Exception as e:
        print(f"[DEBUG] Column check failed: {e}")

    # Pull rows where shot_description_new is not null and keywords_new is null/empty
    cursor.execute(f"""
        SELECT TOP {1 if DEBUG_MODE else BATCH_LIMIT}
               fk_asset,
               keywords
        FROM docketwatch.dbo.damz_test
        WHERE shot_description_new IS NOT NULL
          AND (keywords_new IS NULL OR keywords_new = '')
          AND keywords IS NOT NULL
          AND keywords <> ''
        ORDER BY fk_asset
    """)
    rows = cursor.fetchall()

    if DEBUG_MODE:
        print("[DEBUG MODE] Limiting to 1 record")

    print(f"Found {len(rows)} records to process")
    processed, skipped = 0, 0

    for fk_asset, keywords_raw in rows:
        print(f"\nAsset: {fk_asset}")
        if DEBUG_MODE:
            print(f"[DEBUG] keywords: {str(keywords_raw)[:140]}")

        prompt = build_prompt(rules, keywords_raw)
        cleaned = clean_keywords(prompt, gemini_key)

        if cleaned:
            # Show current before update
            cursor.execute("""
                SELECT keywords_new
                FROM docketwatch.dbo.damz_test
                WHERE fk_asset = ?
            """, (fk_asset,))
            before = cursor.fetchone()
            if DEBUG_MODE:
                print(f"[DEBUG] Before: {before[0] if before else 'NULL'}")

            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET keywords_new = ?
                WHERE fk_asset = ?
            """, (cleaned, fk_asset))
            conn.commit()

            # Verify
            cursor.execute("""
                SELECT keywords_new
                FROM docketwatch.dbo.damz_test
                WHERE fk_asset = ?
            """, (fk_asset,))
            after = cursor.fetchone()
            print(f"OK: {fk_asset} -> {after[0][:100] if after and after[0] else cleaned[:100]}")
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
