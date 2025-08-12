import pyodbc
import google.generativeai as genai
import time

# --- CONFIG ---
BATCH_LIMIT = 1000
GEMINI_MODEL = "gemini-1.5-flash"
TEMPERATURE = 0.6
MAX_TOKENS = 200
SLEEP_SECONDS = 1.5  # Delay to stay polite and safe

# --- Prompt Setup ---
PROMPT_RULES_PATH = "\\\\10.146.176.84\\general\\docketwatch\\python\\prompt_rules.txt"

def load_prompt_rules():
    with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
        return f.read()

# --- Gemini Key Retrieval ---
def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

# --- Prompt Builder ---
def build_prompt(rules, headline, description):
    return f"""{rules}

Headline: {headline}
Shot Description: {description}
"""

# --- Gemini Call ---
def analyze_asset(prompt, gemini_key):
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

        text = response.text.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        type_line = next((l for l in lines if l.lower().startswith("type:")), None)
        headline_line = next((l for l in lines if l.lower().startswith("optimized headline:")), None)

        return (
            type_line.split(":", 1)[1].strip() if type_line else None,
            headline_line.split(":", 1)[1].strip() if headline_line else None
        )

    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        return None, None

# --- Main Logic ---
def main():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    rules = load_prompt_rules()
    gemini_key = get_gemini_key(cursor)
    if not gemini_key:
        print("ERROR: Gemini API key not found.")
        return

    cursor.execute(f"""
    SELECT TOP {BATCH_LIMIT} fk_asset, headline, shot_description
    FROM docketwatch.dbo.damz_test
    WHERE headline_optimized IS NOT NULL
    """)
    rows = cursor.fetchall()

    processed, skipped = 0, 0

    for row in rows:
        fk_asset, headline, shot_description = row
        print(f"\nAnalyzing asset: {fk_asset}")

        prompt = build_prompt(rules, headline, shot_description)
        type_final, headline_final = analyze_asset(prompt, gemini_key)

        if type_final and headline_final:
            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET headline_type_v2 = ?, 
                    headline_v2 = ?
                WHERE fk_asset = ?
            """, (type_final, headline_final, fk_asset))
            conn.commit()
            print(f"✓ Updated: {fk_asset} → {headline_final} ({type_final})")
            processed += 1
        else:
            print(f"⚠ Skipped: {fk_asset} — invalid response")
            skipped += 1

        time.sleep(SLEEP_SECONDS)

    print("\n=== BATCH COMPLETE ===")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()