import pyodbc
import google.generativeai as genai
import re
import time
import os
import sys

# Import centralized Gemini logging functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scraper_base import (
    get_gemini_key,
    gemini_api_call_with_logging,
    get_gemini_usage_stats,
    log_gemini_call
)

# --- CONFIG ---
BATCH_LIMIT = 5000
GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.2  # low for rule-following
MAX_TOKENS = 400   # increased for detailed descriptions
SLEEP_SECONDS = 0.5
DEBUG_MODE = False
SCRIPT_NAME = "clean_shot_description.py"  # For Gemini logging purposes

# --- Prompt Setup ---
PROMPT_RULES_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_shotdesc.txt"

def load_prompt_rules():
    with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
        return f.read()

# --- Get Image Path ---
def get_image_path(cursor, fk_asset):
    cursor.execute("""
        SELECT u.path + i.path AS full_path
        FROM damz.dbo.asset_image i
        JOIN damz.dbo.storage_unit u ON u.id = i.fk_storage_unit
        WHERE i.fk_asset = ?
    """, (fk_asset,))
    row = cursor.fetchone()
    return row[0] if row else None

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

    # max ~30 words for detailed descriptions
    words = s.split()
    if len(words) > 30:
        s = " ".join(words[:30])

    return s

# --- Prompt Builder ---
def build_prompt(rules, headline_v5, shot_description):
    # Headline gives context for names/event normalization. Keep it brief.
    headline_v5 = headline_v5 or ""
    shot_description = shot_description or ""

    return f"""{rules}

ANALYZE THIS IMAGE to create a detailed shot description.

Context (for reference only):
Headline: {headline_v5}
Original_Description: {shot_description}

Please analyze the actual image and provide a detailed, visual shot description following the formatting rules above.
"""

# --- Gemini Call with Vision ---
def clean_shot_description(prompt, image_path, cursor, fk_asset):
    """Clean shot description using Gemini Vision with centralized logging"""
    from datetime import datetime
    
    start_time = datetime.now()
    prompt_length = len(prompt)
    response_length = 0
    success = False
    error_message = None
    input_tokens = None
    output_tokens = None
    total_tokens = None
    response_text = None
    
    try:
        # Get API key using centralized function
        gemini_key = get_gemini_key(cursor)
        if not gemini_key:
            error_message = "Gemini API key not found"
            print(f"[ERROR] {error_message}")
            return None
            
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Check if image file exists
        if not image_path or not os.path.exists(image_path):
            error_message = f"Image not found: {image_path}"
            print(f"[WARNING] {error_message}")
            return None

        # Upload image to Gemini
        try:
            image_file = genai.upload_file(path=image_path)
            if DEBUG_MODE:
                print(f"[DEBUG] Image uploaded: {image_file.name}")
        except Exception as e:
            error_message = f"Failed to upload image {image_path}: {e}"
            print(f"[ERROR] {error_message}")
            return None

        response = model.generate_content(
            [prompt, image_file],
            generation_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": MAX_TOKENS
            }
        )

        response_text = (response.text or "").strip()
        response_length = len(response_text)
        
        # Try to extract token usage if available
        try:
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', None)
                output_tokens = getattr(usage, 'candidates_token_count', None)
                total_tokens = getattr(usage, 'total_token_count', None)
        except Exception as e:
            if DEBUG_MODE:
                print(f"[DEBUG] Could not extract token usage: {e}")
        
        if DEBUG_MODE:
            print(f"[DEBUG] Gemini raw: {response_text}")

        # Use first non-empty line only
        lines = [ln.strip() for ln in response_text.splitlines() if ln.strip()]
        if not lines:
            error_message = "No valid response lines"
            return None

        cleaned = lines[0]
        # defensive strip of quotes and trailing punctuation
        cleaned = cleaned.strip(" '\"")
        cleaned = post_clean(cleaned)

        # Clean up uploaded file
        try:
            genai.delete_file(image_file.name)
        except:
            pass  # Don't fail if cleanup fails

        if cleaned:
            success = True
            return cleaned
        else:
            error_message = "No cleaned output produced"
            return None

    except Exception as e:
        error_message = str(e)
        print(f"[ERROR] Gemini API failed: {e}")
        return None
    
    finally:
        # Log the API call using centralized logging function
        end_time = datetime.now()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        log_gemini_call(
            cursor, fk_asset, prompt_length, response_length, success, 
            error_message, processing_time_ms, input_tokens, output_tokens, total_tokens
        )

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

    # Show recent usage statistics
    stats = get_gemini_usage_stats(cursor, days=7)
    if stats:
        print(f"\n=== RECENT USAGE (Last 7 days) ===")
        print(f"Total calls: {stats['total_calls']}")
        print(f"Successful calls: {stats['successful_calls']}")
        print(f"Total tokens used: {stats['total_tokens']:,}")
        print(f"Estimated cost: ${stats['total_cost']:.4f}")
        print(f"Average response time: {stats['avg_response_time_ms']:.1f}ms")
        print("=" * 50)

    # Confirm target column exists
    try:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'damz_test' AND TABLE_SCHEMA = 'dbo'
              AND COLUMN_NAME IN ('headline_v5','shot_description','shot_description_new_2')
        """)
        cols = {row[0] for row in cursor.fetchall()}
        if 'headline_v5' not in cols:
            print("WARNING: Column 'headline_v5' not found.")
        if 'shot_description_new_2' not in cols:
            print("WARNING: Column 'shot_description_new_2' not found.")
    except Exception as e:
        print(f"[DEBUG] Column check failed: {e}")

    # Pull rows where headline_v5 is not null and shot_description_new_2 is null
    cursor.execute(f"""
        SELECT TOP {1 if DEBUG_MODE else BATCH_LIMIT}
               fk_asset,
               headline_v5,
               shot_description
        FROM docketwatch.dbo.damz_test
        WHERE headline_v5 IS NOT NULL
          AND shot_description_new_2 IS NULL
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

        # Get image path
        image_path = get_image_path(cursor, fk_asset)
        if not image_path:
            print(f"SKIP: {fk_asset} (no image path found)")
            skipped += 1
            continue

        if DEBUG_MODE:
            print(f"[DEBUG] image_path: {image_path}")

        prompt = build_prompt(rules, headline_v5, shot_description)
        cleaned = clean_shot_description(prompt, image_path, cursor, fk_asset)

        if cleaned:
            # Show current before update
            cursor.execute("""
                SELECT shot_description_new_2
                FROM docketwatch.dbo.damz_test
                WHERE fk_asset = ?
            """, (fk_asset,))
            before = cursor.fetchone()
            if DEBUG_MODE:
                print(f"[DEBUG] Before: {before[0] if before else 'NULL'}")

            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET shot_description_new_2 = ?
                WHERE fk_asset = ?
            """, (cleaned, fk_asset))
            conn.commit()

            # Verify
            cursor.execute("""
                SELECT shot_description_new_2
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

    # Show final usage statistics
    final_stats = get_gemini_usage_stats(cursor, days=1)
    if final_stats:
        print(f"\n=== TODAY'S USAGE ===")
        print(f"Total calls today: {final_stats['total_calls']}")
        print(f"Successful calls: {final_stats['successful_calls']}")
        print(f"Total tokens used today: {final_stats['total_tokens']:,}")
        print(f"Estimated cost today: ${final_stats['total_cost']:.4f}")
        print(f"Average response time: {final_stats['avg_response_time_ms']:.1f}ms")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
