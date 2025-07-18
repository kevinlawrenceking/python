import os
import pyodbc
import json
import time
from datetime import datetime
import google.generativeai as genai

# === CONFIG ===
DSN = "Docketwatch"
script_filename = os.path.splitext(os.path.basename(__file__))[0]  # no .py
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
GEMINI_MODEL_NAME = "gemini-1.5-flash"  # Or use "gemini-1.5-pro" if needed

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

# === Gemini API CONFIG ===
def get_gemini_key(cursor):
    """Retrieves the Gemini API key from the database."""
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

# === Fetch Celebrities to Process ===
def get_celebrities():
    cursor.execute("""
        SELECT TOP 300 id, name
        FROM docketwatch.dbo.celebrities
        WHERE legal_name_found = 0 AND legal_name_checked = 0
        ORDER BY priority_score DESC
    """)
    return cursor.fetchall()

# === Helper function to extract JSON from potentially problematic responses ===
def extract_json_from_response(text):
    """
    Tries to extract valid JSON from a text response that might contain markdown or other elements.
    """
    # First, try to find content between JSON brackets
    if '{' in text and '}' in text:
        try:
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass  # Try other methods
    
    # Fallback to a default response if extraction fails
    return {
        "legal_name": "Legal name not confidently found",
        "source": "Could not extract valid JSON from response"
    }

# === Call Gemini to Get Legal Name ===
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
    
    IMPORTANT: Respond with raw JSON only. Do not include markdown formatting, code blocks, backticks, explanations, or any non-JSON content.
    """
    try:
        gemini_api_key = get_gemini_key(cursor)
        if not gemini_api_key:
            log_message("ERROR", "Gemini API key not found")
            return None

        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        generation_config = {"temperature": 0.1, "max_output_tokens": 400}
        
        log_message("DEBUG", f"Sending prompt to Gemini for {celebrity_name}")
        response = model.generate_content(prompt, generation_config=generation_config)
        
        if response:
            result = response.text.strip()
            log_message("DEBUG", f"Gemini response received for {celebrity_name}")
            
            # Remove markdown code block if present
            if result.startswith("```") and "```" in result:
                # Extract content between code block markers
                result = result.split("```", 2)[1]
                if result.startswith("json"):
                    result = result[4:].strip()  # Remove 'json' and any whitespace
                result = result.strip()
                log_message("DEBUG", f"Stripped code block markers from response")
            
            return result
        else:
            log_message("ERROR", f"Empty response from Gemini for {celebrity_name}")
            return None
    except Exception as e:
        log_message("ERROR", f"Gemini API error for {celebrity_name}: {str(e)}")
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
                try:
                    # Try to clean up the response further if needed
                    cleaned_result = result
                    
                    # Check if there are any trailing backticks or other common issues
                    if "```" in cleaned_result:
                        # Get everything up to the last closing backtick
                        cleaned_result = cleaned_result.split("```")[0]
                    
                    # Handle potential extra characters at beginning or end
                    cleaned_result = cleaned_result.strip()
                    
                    log_message("DEBUG", f"Attempting to parse JSON: {cleaned_result[:100]}...")
                    
                    try:
                        response_data = json.loads(cleaned_result)
                    except json.JSONDecodeError:
                        # Try our fallback extractor if standard parsing fails
                        log_message("WARNING", f"Standard JSON parsing failed, trying extraction method")
                        response_data = extract_json_from_response(result)
                    
                    legal_name = response_data.get("legal_name", "")
                    source = response_data.get("source", "")
                    update_database(celeb_id, legal_name, source)
                    log_message("INFO", f"Updated {celeb_name}: {legal_name}")
                except Exception as je:
                    log_message("ERROR", f"Failed to process response for {celeb_name}: {je}")
                    log_message("DEBUG", f"Raw response: {result[:200]}...")
                    update_database(celeb_id, "Legal name not confidently found", "Invalid response format")
            else:
                update_database(celeb_id, "Legal name not confidently found", "No verified legal records available")
                log_message("WARNING", f"No valid legal name found for {celeb_name}")
        except Exception as e:
            log_message("ERROR", f"Error processing {celeb_name}: {e}")
        time.sleep(1.5)

if __name__ == "__main__":
    try:
        # Check that Gemini SDK is properly installed
        if not hasattr(genai, 'GenerativeModel'):
            log_message("ERROR", "Google Generative AI SDK not properly installed. Please run 'pip install google-generativeai'")
            exit(1)
            
        process_celebrities()
        log_message("INFO", "=== Legal Name Finder Script Completed ===")
    except Exception as e:
        log_message("CRITICAL", f"Script failed with error: {str(e)}")
    finally:
        cursor.close()
        conn.close()
