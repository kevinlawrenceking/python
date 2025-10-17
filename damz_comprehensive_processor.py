import pyodbc
import google.generativeai as genai
import re
import time
import os
import json
import argparse
import logging
from datetime import datetime

# --- CONFIG ---
BATCH_LIMIT = 100
MODEL_ID = 1                  # from dbo.gemini_models
# TARGET_VERSION is now determined dynamically by querying damz_test_version_model
TARGET_VERSION = 7           # new test version to insert (e.g., 3, 4, 5)
TEMPERATURE = 0.2
SLEEP_SECONDS = 1.0
DEBUG_MODE = True

VALID_TYPES = {
    "General", "Stock", "Presser", "Commercial", "Government",
    "Police Footage", "Court", "Movie", "Music Video", "Social Media",
    "TV Show", "Live Sports Event", "Live Event", "Print"
}
VALID_EMOTIONS = {
    "HAPPY", "EXCITED", "SERIOUS", "CONFIDENT", "SURPRISED", "ANGRY",
    "SAD", "CONCERNED", "CONTEMPLATIVE", "RELAXED", "PLAYFUL", "NEUTRAL"
}

PROMPT_RULES_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_rules.txt"
PROMPT_SHOTDESC_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_shotdesc.txt"
PROMPT_KEYWORDS_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_keywords.txt"

# Setup logging
LOG_FILE = r"u:\docketwatch\python\logs\damz_processor.log"

def setup_logging():
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Check if running from command line or from ColdFusion
    import sys
    is_interactive = sys.stdout.isatty()
    
    handlers = [logging.FileHandler(LOG_FILE, encoding='utf-8')]
    
    # Only add console handler if running interactively
    if is_interactive:
        handlers.append(logging.StreamHandler())
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    return logging.getLogger(__name__)

def load_prompt_rules():
    logger = logging.getLogger(__name__)
    try:
        logger.info("Loading prompt rules files...")
        with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
            headline_rules = f.read()
        with open(PROMPT_SHOTDESC_PATH, "r", encoding="utf-8") as f:
            shotdesc_rules = f.read()
        with open(PROMPT_KEYWORDS_PATH, "r", encoding="utf-8") as f:
            keywords_rules = f.read()
        logger.info("Prompt rules loaded successfully")
        return headline_rules, shotdesc_rules, keywords_rules
    except Exception as e:
        logger.error(f"Failed to load prompt rules: {e}")
        raise

def get_gemini_key(cursor):
    logger = logging.getLogger(__name__)
    try:
        logger.info("Retrieving Gemini API key from database...")
        cursor.execute("SELECT gemini_api_damz FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        if row and row[0]:
            logger.info("Gemini API key retrieved successfully")
            return row[0]
        else:
            logger.error("Gemini API key not found in database")
            return None
    except Exception as e:
        logger.error(f"Failed to retrieve Gemini API key: {e}")
        return None

def get_gemini_model(cursor, model_id=1):
    cursor.execute("""
        SELECT model_name, display_name, max_tokens, supports_vision
        FROM docketwatch.dbo.gemini_models
        WHERE id = ? AND is_active = 1
    """, (model_id,))
    row = cursor.fetchone()
    if row:
        return {
            "model_name": row[0],
            "display_name": row[1],
            "max_tokens": int(row[2]),
            "supports_vision": bool(row[3])
        }
    print(f"WARNING: Model ID {model_id} not found or inactive, using fallback")
    return {
        "model_name": "gemini-2.5-flash-image",
        "display_name": "Fallback Model",
        "max_tokens": 300,
        "supports_vision": True
    }

def get_image_path(cursor, fk_asset):
    cursor.execute("""
        SELECT u.path + i.path AS full_path
        FROM damz.dbo.asset_image i
        JOIN damz.dbo.storage_unit u ON u.id = i.fk_storage_unit
        WHERE i.type = 'THUMBNAIL' AND i.fk_asset = ?
    """, (fk_asset,))
    row = cursor.fetchone()
    return row[0] if row else None

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

def post_clean_description(text):
    if not text:
        return text
    s = text.strip()
    for pat in CREDIT_PATTERNS + EDITOR_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = s.strip(" ,")
    # Uncomment to limit to 30 words:
    # words = s.split()
    # if len(words) > 30:
    #     s = " ".join(words[:30])
    return s

VAGUE_TERMS = {
    "body", "torso", "booze", "object", "thing", "nice", "cool",
    "stuff", "item", "piece", "element", "part", "area", "section"
}

def post_clean_emotions(arr):
    if not arr:
        return []
    cleaned, seen = [], set()
    for e in arr:
        if not e or not isinstance(e, str):
            continue
        x = e.strip().upper()
        if x in VALID_EMOTIONS and x not in seen:
            seen.add(x)
            cleaned.append(x)
    return cleaned[:3]

def post_clean_keywords(arr):
    if not arr:
        return []
    cleaned, seen = [], set()
    for k in arr:
        if not k or not isinstance(k, str):
            continue
        orig = k.strip()
        low = orig.lower()
        if low in VAGUE_TERMS:
            continue
        if len(orig) < 2 or len(orig) > 50:
            continue
        if low not in seen:
            seen.add(low)
            cleaned.append(orig)
    return cleaned[:15]

def build_comprehensive_prompt(h_rules, sd_rules, kw_rules, headline, shot_description, keywords_raw, custom_notes=None):
    if isinstance(keywords_raw, str):
        try:
            keywords_list = json.loads(keywords_raw)
        except:
            keywords_list = re.split(r'[,;|]', keywords_raw)
    else:
        keywords_list = keywords_raw or []
    keywords_list = [kw.strip() for kw in keywords_list if kw and kw.strip()]

    # Build priority instructions if custom notes provided
    priority_section = ""
    if custom_notes:
        priority_section = f"""
🚨🚨🚨 ABSOLUTE OVERRIDE INSTRUCTIONS 🚨🚨🚨
CRITICAL: The following instructions COMPLETELY OVERRIDE and REPLACE any conflicting rules below.
IGNORE ALL CONTRADICTORY INSTRUCTIONS in the tasks below if they conflict with these priority rules.

{custom_notes}

*** MANDATORY COMPLIANCE ***
You MUST follow these override instructions EXACTLY, even if they contradict the detailed rules in TASK 1, 2, 3, or 4.
These instructions take ABSOLUTE precedence over ALL other formatting, length, or content requirements.
====================================================================

"""

    return f"""You are a comprehensive metadata assistant for DAMZ, a celebrity photo asset system.

{priority_section}

ANALYZE THIS IMAGE along with the provided text data to perform ALL of the following tasks:

TASK 1: HEADLINE TYPE & OPTIMIZATION
{h_rules}

TASK 2: SHOT DESCRIPTION CLEANING
{sd_rules}

TASK 3: KEYWORD CLEANING
{kw_rules}

TASK 4: EMOTION CLASSIFICATION
Use ONLY: HAPPY, EXCITED, SERIOUS, CONFIDENT, SURPRISED, ANGRY, SAD, CONCERNED, CONTEMPLATIVE, RELAXED, PLAYFUL, NEUTRAL

INPUT DATA:
Current Headline: {headline}
Current Shot Description: {shot_description}
Current Keywords: {json.dumps(keywords_list)}

REQUIRED RESPONSE FORMAT (exact):
Type: [one of the valid types]
Optimized_Headline: [final optimized headline]
Shot_Description: [clean, specific description]
Keywords: [JSON array no spaces after commas]
Emotion: [JSON array emotions in ALL CAPS no spaces after commas]
"""

def analyze_comprehensive(prompt, image_path, api_key, model_name, max_tokens):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        if not image_path or not os.path.exists(image_path):
            print(f"[WARNING] Image not found: {image_path}")
            return None, None, None, None, None

        try:
            # Try uploading without display_name first (simpler approach)
            image_file = genai.upload_file(path=image_path)
        except Exception as e:
            # If upload fails with ragStoreName error, try using PIL to load image directly
            print(f"[WARNING] Standard upload failed, trying direct image approach: {e}")
            try:
                from PIL import Image
                img = Image.open(image_path)
                # Use the image directly instead of uploading
                resp = model.generate_content(
                    [prompt, img],
                    generation_config={"temperature": TEMPERATURE, "max_output_tokens": max_tokens}
                )
                text = (getattr(resp, "text", "") or "").strip()
                
                if DEBUG_MODE or not text:
                    print(f"[DEBUG] Gemini raw response: {text[:200]}...")
                
                if not text or len(text.strip()) < 10:
                    print(f"[ERROR] Gemini returned empty or very short response: '{text}'")
                    return None, None, None, None, None
                
                # Skip the normal upload flow and go straight to parsing
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                type_final = headline_final = description_final = keywords_final = emotion_final = None
                
                for ln in lines:
                    low = ln.lower()
                    if low.startswith("type:"):
                        v = ln.split(":", 1)[1].strip()
                        type_final = v if v in VALID_TYPES else "Live Event"
                    elif low.startswith("optimized_headline:") or low.startswith("optimized headline:"):
                        v = ln.split(":", 1)[1].strip()
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        headline_final = v
                    elif low.startswith("shot_description:"):
                        v = ln.split(":", 1)[1].strip()
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        description_final = post_clean_description(v)
                    elif low.startswith("keywords:"):
                        v = ln.split(":", 1)[1].strip()
                        m = re.search(r'\[.*\]', v, re.DOTALL)
                        if m:
                            try:
                                arr = json.loads(m.group())
                                if isinstance(arr, list):
                                    cleaned = post_clean_keywords(arr)
                                    if cleaned:
                                        keywords_final = json.dumps(cleaned, separators=(",", ":"))
                            except json.JSONDecodeError as je:
                                print(f"[ERROR] Keywords JSON parse failed: {je}")
                                continue
                    elif low.startswith("emotion:"):
                        v = ln.split(":", 1)[1].strip()
                        m = re.search(r'\[.*\]', v, re.DOTALL)
                        if m:
                            try:
                                arr = json.loads(m.group())
                                if isinstance(arr, list):
                                    cleaned = post_clean_emotions(arr)
                                    if cleaned:
                                        emotion_final = json.dumps(cleaned, separators=(",", ":"))
                            except json.JSONDecodeError as je:
                                print(f"[ERROR] Emotion JSON parse failed: {je}")
                                continue
                
                if DEBUG_MODE:
                    print(f"[DEBUG] Parsed results: Type={type_final}, Headline={headline_final is not None}, Desc={description_final is not None}, Keywords={keywords_final is not None}, Emotion={emotion_final is not None}")
                
                return type_final, headline_final, description_final, keywords_final, emotion_final
                
            except Exception as pil_error:
                print(f"[ERROR] Direct image approach also failed: {pil_error}")
                return None, None, None, None, None

        resp = model.generate_content(
            [prompt, image_file],
            generation_config={"temperature": TEMPERATURE, "max_output_tokens": max_tokens}
        )
        
        # Check if response has text attribute
        if not hasattr(resp, 'text'):
            print(f"[ERROR] Response object has no 'text' attribute")
            print(f"[DEBUG] Response object type: {type(resp)}")
            print(f"[DEBUG] Response dir: {dir(resp)}")
            if hasattr(resp, 'candidates'):
                print(f"[DEBUG] Candidates: {resp.candidates}")
            return None, None, None, None, None
            
        text = (getattr(resp, "text", "") or "").strip()

        try:
            genai.delete_file(image_file.name)
        except:
            pass

        if DEBUG_MODE or not text:
            print(f"[DEBUG] Gemini raw response: {text[:200]}...")

        if not text or len(text.strip()) < 10:
            print(f"[ERROR] Gemini returned empty or very short response: '{text}'")
            return None, None, None, None, None

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        type_final = headline_final = description_final = keywords_final = emotion_final = None

        for ln in lines:
            low = ln.lower()
            if DEBUG_MODE:
                print(f"[DEBUG] Parsing line: '{ln}'")
                print(f"[DEBUG] Lowercase: '{low}'")
            if low.startswith("type:"):
                v = ln.split(":", 1)[1].strip()
                type_final = v if v in VALID_TYPES else "Live Event"
            elif low.startswith("optimized_headline:") or low.startswith("optimized headline:"):
                v = ln.split(":", 1)[1].strip()
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                headline_final = v
                if DEBUG_MODE:
                    print(f"[DEBUG] Matched headline: '{headline_final}'")
            elif low.startswith("shot_description:"):
                v = ln.split(":", 1)[1].strip()
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                description_final = post_clean_description(v)
            elif low.startswith("keywords:"):
                v = ln.split(":", 1)[1].strip()
                m = re.search(r'\[.*\]', v, re.DOTALL)
                if m:
                    try:
                        arr = json.loads(m.group())
                        if isinstance(arr, list):
                            cleaned = post_clean_keywords(arr)
                            if cleaned:
                                keywords_final = json.dumps(cleaned, separators=(",", ":"))
                    except json.JSONDecodeError as je:
                        print(f"[ERROR] Keywords JSON parse failed: {je}")
                        print(f"[DEBUG] Raw keywords text: {m.group()}")
                        continue
            elif low.startswith("emotion:"):
                v = ln.split(":", 1)[1].strip()
                m = re.search(r'\[.*\]', v, re.DOTALL)
                if m:
                    try:
                        arr = json.loads(m.group())
                        if isinstance(arr, list):
                            cleaned = post_clean_emotions(arr)
                            if cleaned:
                                emotion_final = json.dumps(cleaned, separators=(",", ":"))
                    except json.JSONDecodeError as je:
                        print(f"[ERROR] Emotion JSON parse failed: {je}")
                        print(f"[DEBUG] Raw emotion text: {m.group()}")
                        continue

        if DEBUG_MODE:
            print(f"[DEBUG] Parsed results: Type={type_final}, Headline={headline_final is not None}, Desc={description_final is not None}, Keywords={keywords_final is not None}, Emotion={emotion_final is not None}")

        return type_final, headline_final, description_final, keywords_final, emotion_final
    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        return None, None, None, None, None

def get_latest_version_config(cursor):
    """Get the latest version configuration (version, model, notes)"""
    logger = logging.getLogger(__name__)
    try:
        logger.info("Retrieving latest version configuration...")
        cursor.execute("""
            SELECT TOP 1 version, fk_model, prompt_notes
            FROM docketwatch.dbo.damz_test_version_model
            ORDER BY version DESC
        """)
        row = cursor.fetchone()
        if row:
            version, model_id, notes = row[0], row[1], row[2]
            logger.info(f"Using latest version config: version={version}, model_id={model_id}")
            if notes:
                logger.info(f"Custom prompt notes: {notes[:100]}...")
            return version, model_id, notes
        else:
            logger.error("No version configuration found in damz_test_version_model table")
            return None, None, None
    except Exception as e:
        logger.error(f"Failed to retrieve version configuration: {e}")
        return None, None, None





def main():
    # Setup logging first
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("DAMZ Comprehensive Processor Starting")
    logger.info(f"Start time: {datetime.now()}")
    
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Process DAMZ comprehensive metadata")
        parser.add_argument("--fk_asset", type=str, help="Process specific asset by fk_asset ID (optional)")
        args = parser.parse_args()
        
        logger.info(f"Command line args: {args}")
        
        logger.info("Connecting to database...")
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        logger.info("Database connection established")

        h_rules, sd_rules, kw_rules = load_prompt_rules()

        api_key = get_gemini_key(cursor)
        if not api_key:
            logger.error("Gemini API key not found")
            return

        # get latest version configuration
        target_version, latest_model_id, prompt_notes = get_latest_version_config(cursor)
        if target_version is None:
            logger.error("Could not retrieve version configuration")
            return
        
        # determine which model to use
        effective_model_id = latest_model_id if latest_model_id else MODEL_ID
        if latest_model_id and latest_model_id != MODEL_ID:
            logger.info(f"Using model from version config (ID {latest_model_id}) instead of script default (ID {MODEL_ID})")
        
        # get model configuration
        model_cfg = get_gemini_model(cursor, effective_model_id)
        if not model_cfg["supports_vision"]:
            logger.error("Selected model does not support vision")
            return
        logger.info(f"Using model: {model_cfg['display_name']} ({model_cfg['model_name']})")

        # pull version 0 baselines that do not yet have target_version
        if args.fk_asset:
            # Process specific asset
            logger.info(f"Processing specific asset: {args.fk_asset}")
            cursor.execute("""
                SELECT fk_asset, headline, shot_description, keywords
                FROM dbo.damz_test
                WHERE version = 0 AND fk_asset = ?
                  AND NOT EXISTS (
                        SELECT 1
                        FROM dbo.damz_test AS x
                        WHERE x.fk_asset = ? AND x.version = ?
                  )
            """, (args.fk_asset, args.fk_asset, target_version))
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No version 0 record found for fk_asset {args.fk_asset}, or version {target_version} already exists")
                return
        else:
            # Process batch of records
            cursor.execute(f"""
                WITH base AS (
                    SELECT TOP {1 if DEBUG_MODE else BATCH_LIMIT}
                           t.fk_asset, t.headline, t.shot_description, t.keywords
                    FROM dbo.damz_test AS t
                    WHERE t.version = 0
                      AND NOT EXISTS (
                            SELECT 1
                            FROM dbo.damz_test AS x
                            WHERE x.fk_asset = t.fk_asset AND x.version = ?
                      )
                    ORDER BY t.fk_asset
                )
                SELECT fk_asset, headline, shot_description, keywords FROM base;
            """, (target_version,))
            rows = cursor.fetchall()

        logger.info(f"Found {len(rows)} version 0 rows to process for version {target_version}")
        processed = skipped = 0

        for fk_asset, headline, shot_description, keywords in rows:
            logger.info(f"Processing asset: {fk_asset}")
            if DEBUG_MODE and prompt_notes:
                logger.debug(f"Using prompt notes: {prompt_notes}")

            image_path = get_image_path(cursor, fk_asset)
            if not image_path:
                logger.warning(f"SKIP: {fk_asset} (no image path)")
                skipped += 1
                continue
            
            logger.info(f"Image path: {image_path}")

            logger.info("Building comprehensive prompt...")
            prompt = build_comprehensive_prompt(h_rules, sd_rules, kw_rules, headline, shot_description, keywords, prompt_notes)
            
            logger.info("Calling Gemini API for analysis...")
            t_final, h_final, d_final, k_final, e_final = analyze_comprehensive(prompt, image_path, api_key, model_cfg["model_name"], model_cfg["max_tokens"])

            if t_final and h_final and d_final and k_final and e_final:
                cursor.execute("""
                INSERT INTO dbo.damz_test (
                    fk_asset, status, headline, shot_description, headline_type,
                    imported_at, approved, flagged, keywords, version, emotion, agency
                )
                SELECT
                    v0.fk_asset,
                    v0.status,
                    ?, ?, ?, SYSDATETIMEOFFSET(),
                    0, 0,
                    ?, ?, ?, v0.agency
                FROM dbo.damz_test AS v0
                WHERE v0.fk_asset = ? AND v0.version = 0
                  AND NOT EXISTS (
                        SELECT 1 FROM dbo.damz_test z
                        WHERE z.fk_asset = v0.fk_asset AND z.version = ?
                  );
                """, (h_final, d_final, t_final, k_final, target_version, e_final, fk_asset, target_version))
                conn.commit()

                print(f"OK: {fk_asset}")
                processed += 1
            else:
                print(f"SKIP: {fk_asset} (incomplete ai output)")
                skipped += 1

            time.sleep(SLEEP_SECONDS)

        logger.info("=" * 30)
        logger.info("BATCH COMPLETE")
        logger.info(f"Processed: {processed}")
        logger.info(f"Skipped:   {skipped}")
        logger.info(f"End time: {datetime.now()}")

        # Simple success message for ColdFusion
        print(f"SUCCESS: Processed {processed} assets, Skipped {skipped}")

        cursor.close()
        conn.close()
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Fatal error in main(): {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    main()
