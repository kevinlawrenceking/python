import pyodbc
import google.generativeai as genai
import time

# --- CONFIG ---
BATCH_LIMIT = 1000
GEMINI_MODEL = "gemini-1.5-flash"
TEMPERATURE = 0.6
MAX_TOKENS = 500  # Increased from 200 to allow fuller responses
SLEEP_SECONDS = 1.5  # Delay to stay polite and safe
DEBUG_MODE = False  # Set to False for normal operation

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

Please respond in exactly this format:
Type: [your type classification]
Optimized Headline: [your optimized headline]
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
        print(f"[DEBUG] Gemini Response: {text}")  # Show full response now
        
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # Try to find Type and Optimized Headline lines
        type_line = next((l for l in lines if l.lower().startswith("type:")), None)
        headline_line = next((l for l in lines if l.lower().startswith("optimized headline:")), None)
        
        # If standard format not found, try alternative formats
        if not type_line:
            # Maybe it's just a single line response, try to parse it
            if len(lines) == 1 and "," in lines[0]:
                parts = lines[0].split(",")
                if len(parts) >= 2:
                    print(f"[DEBUG] Attempting to parse single-line response: {lines[0]}")
                    # For now, let's try a simple fallback
                    type_final = parts[-1].strip()  # Last part might be type
                    headline_final = ",".join(parts[:-1]).strip()  # Everything else as headline
                    print(f"[DEBUG] Parsed as - Type: '{type_final}', Headline: '{headline_final}'")
                    return type_final, headline_final

        if not type_line:
            print(f"[DEBUG] No 'Type:' line found. Available lines: {[l[:100] for l in lines[:5]]}")
        if not headline_line:
            print(f"[DEBUG] No 'Optimized Headline:' line found. Available lines: {[l[:100] for l in lines[:5]]}")

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
    print(f"[DEBUG] Prompt rules loaded: {len(rules)} characters")
    if DEBUG_MODE:
        print(f"[DEBUG] Prompt rules preview: {rules[:300]}...")
    
    gemini_key = get_gemini_key(cursor)
    if not gemini_key:
        print("ERROR: Gemini API key not found.")
        return

    # Check if the target columns exist
    try:
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'damz_test' AND TABLE_SCHEMA = 'dbo'
            AND COLUMN_NAME IN ('headline_type_v2', 'headline_v2')
        """)
        columns = [row[0] for row in cursor.fetchall()]
        print(f"[DEBUG] Available target columns: {columns}")
        if 'headline_type_v2' not in columns:
            print("WARNING: Column 'headline_type_v2' does not exist!")
        if 'headline_v2' not in columns:
            print("WARNING: Column 'headline_v2' does not exist!")
    except Exception as e:
        print(f"[DEBUG] Could not check columns: {e}")

    cursor.execute(f"""
    SELECT TOP {1 if DEBUG_MODE else BATCH_LIMIT} fk_asset, headline, shot_description
    FROM docketwatch.dbo.damz_test
    WHERE headline_final is not null
    """)
    rows = cursor.fetchall()
    
    if DEBUG_MODE:
        print(f"[DEBUG MODE] Processing only 1 record for testing...")
    
    print(f"Found {len(rows)} records to process")

    processed, skipped = 0, 0

    for row in rows:
        fk_asset, headline, shot_description = row
        print(f"\nAnalyzing asset: {fk_asset}")
        print(f"[DEBUG] Headline: {headline[:100]}...")
        print(f"[DEBUG] Description: {shot_description[:100] if shot_description else 'None'}...")

        prompt = build_prompt(rules, headline, shot_description)
        print(f"[DEBUG] Prompt length: {len(prompt)} characters")
        
        type_final, headline_final = analyze_asset(prompt, gemini_key)

        if type_final and headline_final:
            # First, let's verify the record exists and show current values
            cursor.execute("""
                SELECT headline_type_v2, headline_v2 
                FROM docketwatch.dbo.damz_test 
                WHERE fk_asset = ?
            """, (fk_asset,))
            current_values = cursor.fetchone()
            print(f"[DEBUG] Current DB values - Type: {current_values[0] if current_values else 'NULL'}, Headline: {current_values[1] if current_values else 'NULL'}")
            
            # Now update
            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET headline_type_v2 = ?, 
                    headline_v2 = ?
                WHERE fk_asset = ?
            """, (type_final, headline_final, fk_asset))
            
            rows_affected = cursor.rowcount
            conn.commit()
            
            # Verify the update worked
            cursor.execute("""
                SELECT headline_type_v2, headline_v2 
                FROM docketwatch.dbo.damz_test 
                WHERE fk_asset = ?
            """, (fk_asset,))
            updated_values = cursor.fetchone()
            
            print(f"[DEBUG] Rows affected: {rows_affected}")
            print(f"[DEBUG] Updated DB values - Type: {updated_values[0] if updated_values else 'NULL'}, Headline: {updated_values[1] if updated_values else 'NULL'}")
            print(f"✓ Updated: {fk_asset} → {headline_final} ({type_final})")
            processed += 1
        else:
            print(f"⚠ Skipped: {fk_asset} — Type: {type_final}, Headline: {headline_final}")
            skipped += 1

        time.sleep(SLEEP_SECONDS)

    print("\n=== BATCH COMPLETE ===")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()