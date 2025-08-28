import pyodbc
import google.generativeai as genai
import time
import os
from datetime import datetime

# --- CONFIG ---
BATCH_LIMIT = 5000
GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.2  # Lower temperature for more consistent, rule-following behavior
MAX_TOKENS = 350  # Increased from 200 to allow fuller responses
SLEEP_SECONDS = .5  # Delay to stay polite and safe
DEBUG_MODE = False  # Set to False for normal operation
SCRIPT_NAME = "analyze_damz_gemini.py"  # For logging purposes

# Valid headline types from prompt rules
VALID_TYPES = {
    "General", "Stock", "Presser", "Commercial", "Government", 
    "Police Footage", "Court", "Movie", "Music Video", "Social Media", 
    "TV Show", "Live Sports Event", "Live Event", "Print"
}

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

# --- Gemini API Logging ---
def log_gemini_call(cursor, fk_asset, prompt_length, response_length, success, error_message=None, processing_time_ms=None, input_tokens=None, output_tokens=None, total_tokens=None):
    """Log Gemini API call details to database"""
    try:
        # Calculate cost estimate based on model pricing (approximate)
        cost_estimate = None
        if total_tokens:
            # Gemini 2.5 Flash pricing (as of 2025) - approximate $0.002 per 1K tokens
            cost_estimate = (total_tokens / 1000) * 0.002
        
        cursor.execute("""
            INSERT INTO docketwatch.dbo.gemini_api_log 
            (script_name, model_name, fk_asset, prompt_length, response_length, 
             input_tokens, output_tokens, total_tokens, temperature, max_tokens, 
             success, error_message, processing_time_ms, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            SCRIPT_NAME, GEMINI_MODEL, fk_asset, prompt_length, response_length,
            input_tokens, output_tokens, total_tokens, TEMPERATURE, MAX_TOKENS,
            success, error_message, processing_time_ms, cost_estimate
        ))
        cursor.connection.commit()
        
        if DEBUG_MODE:
            print(f"[DEBUG] Logged API call - Tokens: {total_tokens}, Cost: ${cost_estimate:.6f}" if cost_estimate else "[DEBUG] Logged API call")
            
    except Exception as e:
        print(f"[WARNING] Failed to log API call: {e}")

# --- Get Usage Statistics ---
def get_usage_stats(cursor, days=7):
    """Get recent usage statistics"""
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
                SUM(ISNULL(total_tokens, 0)) as total_tokens,
                SUM(ISNULL(cost_estimate, 0)) as estimated_cost,
                AVG(processing_time_ms) as avg_processing_time
            FROM docketwatch.dbo.gemini_api_log 
            WHERE call_timestamp >= DATEADD(day, -?, GETDATE())
            AND script_name = ?
        """, (days, SCRIPT_NAME))
        
        row = cursor.fetchone()
        if row:
            return {
                'total_calls': row[0] or 0,
                'successful_calls': row[1] or 0,
                'total_tokens': row[2] or 0,
                'estimated_cost': float(row[3] or 0),
                'avg_processing_time': float(row[4] or 0)
            }
    except Exception as e:
        print(f"[WARNING] Failed to get usage stats: {e}")
    
    return None

# --- Prompt Builder ---
def build_prompt(rules, headline, description):
    return f"""{rules}

ANALYZE THIS ASSET:
Current Headline: {headline}
Shot Description: {description}

INSTRUCTIONS:
1. First determine the correct headline TYPE using the decision priority order above
2. Then create an optimized headline following the exact format rules for that type
3. Use the CRITICAL FORMATTING FIXES to avoid common errors

REQUIRED RESPONSE FORMAT (must be exact):
Type: [your type classification]
Optimized Headline: [your optimized headline]

REMEMBER: 80% should be Live Event. When in doubt, choose Live Event.
"""

# --- Gemini Call ---
def analyze_asset(prompt, gemini_key, cursor, fk_asset):
    start_time = datetime.now()
    prompt_length = len(prompt)
    response_length = 0
    success = False
    error_message = None
    input_tokens = None
    output_tokens = None
    total_tokens = None
    
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
        response_length = len(text)
        
        # Try to extract token usage if available
        try:
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', None)
                output_tokens = getattr(usage, 'candidates_token_count', None)
                total_tokens = getattr(usage, 'total_token_count', None)
                
                if DEBUG_MODE and total_tokens:
                    print(f"[DEBUG] Token usage - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}")
        except Exception as e:
            if DEBUG_MODE:
                print(f"[DEBUG] Could not extract token usage: {e}")
        
        print(f"[DEBUG] Gemini Response: {text}")
        
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # Try to find Type and Optimized Headline lines
        type_line = next((l for l in lines if l.lower().startswith("type:")), None)
        headline_line = next((l for l in lines if l.lower().startswith("optimized headline:")), None)
        
        # Extract values
        type_final = None
        headline_final = None
        
        if type_line:
            type_final = type_line.split(":", 1)[1].strip()
            # Validate type against known valid types
            if type_final not in VALID_TYPES:
                print(f"[WARNING] Invalid type '{type_final}', defaulting to 'Live Event'")
                type_final = "Live Event"
        
        if headline_line:
            headline_final = headline_line.split(":", 1)[1].strip()
            # Basic headline validation - remove quotes if present
            if headline_final.startswith('"') and headline_final.endswith('"'):
                headline_final = headline_final[1:-1]
        
        # If standard format not found, try alternative parsing
        if not type_line or not headline_line:
            print(f"[DEBUG] Standard format not found. Available lines: {[l[:100] for l in lines[:5]]}")
            
            # Try single line format
            if len(lines) == 1 and "," in lines[0]:
                parts = lines[0].split(",")
                if len(parts) >= 2:
                    print(f"[DEBUG] Attempting to parse single-line response: {lines[0]}")
                    potential_type = parts[-1].strip()
                    potential_headline = ",".join(parts[:-1]).strip()
                    
                    if potential_type in VALID_TYPES:
                        type_final = potential_type
                        headline_final = potential_headline
                        print(f"[DEBUG] Successfully parsed single-line - Type: '{type_final}', Headline: '{headline_final}'")
                    else:
                        print(f"[DEBUG] Single-line parse failed - invalid type: '{potential_type}'")

        # Final validation
        if not type_final or not headline_final:
            print(f"[ERROR] Failed to parse response - Type: {type_final}, Headline: {headline_final}")
            error_message = f"Failed to parse response - Type: {type_final}, Headline: {headline_final}"
        else:
            success = True
            
    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        error_message = str(e)
        type_final = None
        headline_final = None
    
    finally:
        # Calculate processing time
        end_time = datetime.now()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Log the API call
        log_gemini_call(
            cursor, fk_asset, prompt_length, response_length, success, 
            error_message, processing_time_ms, input_tokens, output_tokens, total_tokens
        )
    
    return type_final, headline_final

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

    # Show recent usage statistics
    stats = get_usage_stats(cursor, days=7)
    if stats:
        print(f"\n=== RECENT USAGE (Last 7 days) ===")
        print(f"Total calls: {stats['total_calls']}")
        print(f"Successful calls: {stats['successful_calls']}")
        print(f"Total tokens used: {stats['total_tokens']:,}")
        print(f"Estimated cost: ${stats['estimated_cost']:.6f}")
        print(f"Avg processing time: {stats['avg_processing_time']:.1f}ms")
        print("=" * 40)

    # Check if the target columns exist
    try:
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'damz_test' AND TABLE_SCHEMA = 'dbo'
            AND COLUMN_NAME IN ('headline_type_V5', 'headline_V5')
        """)
        columns = [row[0] for row in cursor.fetchall()]
        print(f"[DEBUG] Available target columns: {columns}")
        if 'headline_type_V5' not in columns:
            print("WARNING: Column 'headline_type_V5' does not exist!")
        if 'headline_V5' not in columns:
            print("WARNING: Column 'headline_V5' does not exist!")
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
        
        type_final, headline_final = analyze_asset(prompt, gemini_key, cursor, fk_asset)

        if type_final and headline_final:
            # First, let's verify the record exists and show current values
            cursor.execute("""
                SELECT headline_type_V5, headline_V5 
                FROM docketwatch.dbo.damz_test 
                WHERE fk_asset = ?
            """, (fk_asset,))
            current_values = cursor.fetchone()
            print(f"[DEBUG] Current DB values - Type: {current_values[0] if current_values else 'NULL'}, Headline: {current_values[1] if current_values else 'NULL'}")
            
            # Now update
            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET headline_type_V5 = ?, 
                    headline_V5 = ?
                WHERE fk_asset = ?
            """, (type_final, headline_final, fk_asset))
            
            rows_affected = cursor.rowcount
            conn.commit()
            
            # Verify the update worked
            cursor.execute("""
                SELECT headline_type_V5, headline_V5 
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

    # Show final usage statistics
    final_stats = get_usage_stats(cursor, days=1)
    if final_stats:
        print(f"\n=== TODAY'S USAGE ===")
        print(f"Total calls today: {final_stats['total_calls']}")
        print(f"Successful calls: {final_stats['successful_calls']}")
        print(f"Total tokens used today: {final_stats['total_tokens']:,}")
        print(f"Estimated cost today: ${final_stats['estimated_cost']:.6f}")

    print("\n=== BATCH COMPLETE ===")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()