import pyodbc
import google.generativeai as genai
import re
import time
import os
import json

# --- CONFIG ---
BATCH_LIMIT = 5000
GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.2  # low for rule-following
MAX_TOKENS = 300   # increased for comprehensive analysis
SLEEP_SECONDS = 1.0  # slightly longer for complex processing
DEBUG_MODE = False

# Valid headline types from prompt rules
VALID_TYPES = {
    "General", "Stock", "Presser", "Commercial", "Government", 
    "Police Footage", "Court", "Movie", "Music Video", "Social Media", 
    "TV Show", "Live Sports Event", "Live Event", "Print"
}

# Valid emotions for classification
VALID_EMOTIONS = {
    "HAPPY", "EXCITED", "SERIOUS", "CONFIDENT", "SURPRISED", "ANGRY", 
    "SAD", "CONCERNED", "CONTEMPLATIVE", "RELAXED", "PLAYFUL", "NEUTRAL"
}

# --- Prompt Setup ---
PROMPT_RULES_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_rules.txt"
PROMPT_SHOTDESC_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_shotdesc.txt"
PROMPT_KEYWORDS_PATH = r"\\10.146.176.84\general\docketwatch\python\prompt_keywords.txt"

def load_prompt_rules():
    with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
        headline_rules = f.read()
    with open(PROMPT_SHOTDESC_PATH, "r", encoding="utf-8") as f:
        shotdesc_rules = f.read()
    with open(PROMPT_KEYWORDS_PATH, "r", encoding="utf-8") as f:
        keywords_rules = f.read()
    return headline_rules, shotdesc_rules, keywords_rules

# --- Gemini Key Retrieval ---
def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

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

# --- Cleanup Functions ---
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

VAGUE_TERMS = {
    "body", "torso", "booze", "object", "thing", "nice", "cool", 
    "stuff", "item", "piece", "element", "part", "area", "section"
}

def post_clean_emotions(emotions_array):
    if not emotions_array:
        return []
    cleaned = []
    seen = set()
    for emotion in emotions_array:
        if not emotion or not isinstance(emotion, str):
            continue
        # Convert to uppercase and clean
        emotion_clean = emotion.strip().upper()
        # Validate against known emotions
        if emotion_clean in VALID_EMOTIONS and emotion_clean not in seen:
            seen.add(emotion_clean)
            cleaned.append(emotion_clean)
    # Limit to 3 emotions max (rarely more than 3 distinct emotions in one photo)
    return cleaned[:3]

def post_clean_keywords(keywords_array):
    if not keywords_array:
        return []
    cleaned = []
    seen = set()
    for keyword in keywords_array:
        if not keyword or not isinstance(keyword, str):
            continue
        # Preserve original keyword with proper spacing
        original_keyword = keyword.strip()
        # Use lowercase for deduplication check only
        kw_lower = original_keyword.lower()
        # Skip vague terms
        if kw_lower in VAGUE_TERMS:
            continue
        # Skip if too short or too long
        if len(original_keyword) < 2 or len(original_keyword) > 50:
            continue
        # Deduplicate (case insensitive) but preserve original spacing
        if kw_lower not in seen:
            seen.add(kw_lower)
            cleaned.append(original_keyword)
    # Limit to 15 keywords max
    return cleaned[:15]
    if not keywords_array:
        return []
    cleaned = []
    seen = set()
    for keyword in keywords_array:
        if not keyword or not isinstance(keyword, str):
            continue
        # Preserve original keyword with proper spacing
        original_keyword = keyword.strip()
        # Use lowercase for deduplication check only
        kw_lower = original_keyword.lower()
        # Skip vague terms
        if kw_lower in VAGUE_TERMS:
            continue
        # Skip if too short or too long
        if len(original_keyword) < 2 or len(original_keyword) > 50:
            continue
        # Deduplicate (case insensitive) but preserve original spacing
        if kw_lower not in seen:
            seen.add(kw_lower)
            cleaned.append(original_keyword)
    # Limit to 15 keywords max
    return cleaned[:15]

# --- Comprehensive Prompt Builder ---
def build_comprehensive_prompt(headline_rules, shotdesc_rules, keywords_rules, headline, shot_description, keywords_raw):
    # Parse keywords from string if needed
    if isinstance(keywords_raw, str):
        try:
            keywords_list = json.loads(keywords_raw)
        except:
            keywords_list = re.split(r'[,;|]', keywords_raw)
    else:
        keywords_list = keywords_raw or []
    
    keywords_list = [kw.strip() for kw in keywords_list if kw and kw.strip()]

    return f"""You are a comprehensive metadata assistant for DAMZ, a celebrity photo asset system.

ANALYZE THIS IMAGE along with the provided text data to perform ALL of the following tasks:

TASK 1: HEADLINE TYPE & OPTIMIZATION
{headline_rules}

**CRITICAL HEADLINE REQUIREMENTS FROM ANALYSIS:**
- Include MAIN EVENT description (not just names and locations)
- For family photos: include relationship context like "with Daughters" 
- For sports: include team/player that won and activity
- For court cases: include "Criminal", "Sentencing", or case type
- For TV shows: include episode type like "Interview", "Monologue"
- Keep Day # if it's part of the event name
- Use full stage names like "A$AP Rocky" not shortened versions

TASK 2: SHOT DESCRIPTION CLEANING  
{shotdesc_rules}

**CRITICAL SHOT DESCRIPTION REQUIREMENTS FROM ANALYSIS:**
- ALWAYS use first AND last names (not just last names)
- Include specific clothing details: "light-blue Alo onesie", "red Trump 2024 campaign shirt"
- Describe actions: "rips open his shirt", "exchanges punches", "celebrates wildly"
- Include facial expressions: "smiling broadly", "serious expression", "jubilant expressions"
- Preserve venue names: "Hackney Town Hall", "Citizens Bank Park", "Dorothy Chandler Pavilion"
- Include relationship context: "with daughters Sami and Eloise", "with boyfriend Henry Junior"
- Describe setting: "on stage", "on red carpet", "at defense table", "on beach"

TASK 3: KEYWORD CLEANING
{keywords_rules}

**CRITICAL KEYWORD REQUIREMENTS FROM ANALYSIS:**
- REMOVE ALL celebrity names, band names, years, dates, and specific city names
- REMOVE overly specific phrases like "Famously Super Slim Cut", "Big Tech Boyfriend Ted Dhanik"
- FOCUS ON: clothing, actions, expressions, objects, general settings
- FIX MISSPELLINGS: "Oesie" → "Onesie"
- CONSOLIDATE: "Flops", "Flip-flops" → "Flip Flops"
- MAX 10-15 keywords focusing on visual elements only

TASK 4: EMOTION CLASSIFICATION
Analyze facial expressions and body language in the image. Use ONLY these emotions:
HAPPY, EXCITED, SERIOUS, CONFIDENT, SURPRISED, ANGRY, SAD, CONCERNED, CONTEMPLATIVE, RELAXED, PLAYFUL, NEUTRAL

Rules for emotion classification:
- Focus on the most prominent person's facial expression
- Look for: smile intensity, eye contact, posture, gesture
- If multiple people show different emotions, list up to 3 most prominent
- Return as JSON array with emotions in ALL CAPS
- Examples: ["HAPPY"], ["SERIOUS","CONFIDENT"], ["EXCITED","PLAYFUL"]

INPUT DATA:
Current Headline: {headline}
Current Shot Description: {shot_description}
Current Keywords: {json.dumps(keywords_list)}

INSTRUCTIONS:
1. ANALYZE the actual image first - look at faces, clothing, setting, actions
2. Determine correct headline type (80% should be "Live Event")
3. Create optimized headline with MAIN EVENT included (not just names/locations)
4. Generate detailed shot description with first+last names, specific details, relationships
5. Clean keywords to remove names/dates/cities, focus on visual elements only
6. Classify emotions based on actual facial expressions in the image

REQUIRED RESPONSE FORMAT (must be exact):
Type: [headline type from valid list]
Optimized_Headline: [optimized headline with main event described]
Shot_Description: [detailed visual description with first+last names and specifics]
Keywords: [compact JSON array with no spaces after commas, visual elements only]
Emotion: [JSON array of emotions in ALL CAPS with no spaces after commas]

ANALYSIS-BASED EXAMPLES:
- Headline: "2025, Corrigan, Beverly Hills" → "Corrigan Leaves Workout in Skintight Blue Onesie, Sparking Pregnancy Rumors with Visible Bump"
- Shot Description: Include "Joy Corrigan" not just "Corrigan", "light-blue Alo onesie", "visible baby bump"
- Keywords: Remove "Joy Corrigan","Beverly Hills","2025" → Keep "Pregnant","Baby Bump","Onesie","Light Blue","Sunglasses"
- Emotion: Look at her actual facial expression in the image

REMEMBER: 
- Use the IMAGE as the primary source of truth for all decisions
- Include WHAT IS HAPPENING (main event) not just WHO and WHERE
- Remove all celebrity names from keywords - focus on visual descriptors only
- Be specific about clothing, expressions, and actions you can see
"""

# --- Comprehensive Gemini Analysis ---
def analyze_comprehensive(prompt, image_path, gemini_key):
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Check if image file exists
        if not image_path or not os.path.exists(image_path):
            print(f"[WARNING] Image not found: {image_path}")
            return None, None, None, None, None

        # Upload image to Gemini
        try:
            image_file = genai.upload_file(path=image_path)
            if DEBUG_MODE:
                print(f"[DEBUG] Image uploaded: {image_file.name}")
        except Exception as e:
            print(f"[ERROR] Failed to upload image {image_path}: {e}")
            return None, None, None, None, None

        response = model.generate_content(
            [prompt, image_file],
            generation_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": MAX_TOKENS
            }
        )

        text = (response.text or "").strip()
        if DEBUG_MODE:
            print(f"[DEBUG] Gemini raw response: {text}")

        # Parse the structured response
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        type_final = None
        headline_final = None
        description_final = None
        keywords_final = None
        emotion_final = None
        
        # Extract each component
        for line in lines:
            if line.lower().startswith("type:"):
                type_final = line.split(":", 1)[1].strip()
                if type_final not in VALID_TYPES:
                    print(f"[WARNING] Invalid type '{type_final}', defaulting to 'Live Event'")
                    type_final = "Live Event"
            elif line.lower().startswith("optimized_headline:"):
                headline_final = line.split(":", 1)[1].strip()
                if headline_final.startswith('"') and headline_final.endswith('"'):
                    headline_final = headline_final[1:-1]
            elif line.lower().startswith("shot_description:"):
                description_final = line.split(":", 1)[1].strip()
                if description_final.startswith('"') and description_final.endswith('"'):
                    description_final = description_final[1:-1]
                description_final = post_clean_description(description_final)
            elif line.lower().startswith("keywords:"):
                keywords_raw = line.split(":", 1)[1].strip()
                try:
                    # Find JSON array in response
                    json_match = re.search(r'\[.*\]', keywords_raw, re.DOTALL)
                    if json_match:
                        keywords_array = json.loads(json_match.group())
                        if isinstance(keywords_array, list):
                            cleaned = post_clean_keywords(keywords_array)
                            if cleaned:
                                keywords_final = json.dumps(cleaned, separators=(',', ':'))
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Keywords JSON parse failed: {e}")
            elif line.lower().startswith("emotion:"):
                emotion_raw = line.split(":", 1)[1].strip()
                try:
                    # Find JSON array in response
                    json_match = re.search(r'\[.*\]', emotion_raw, re.DOTALL)
                    if json_match:
                        emotions_array = json.loads(json_match.group())
                        if isinstance(emotions_array, list):
                            cleaned = post_clean_emotions(emotions_array)
                            if cleaned:
                                emotion_final = json.dumps(cleaned, separators=(',', ':'))
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Emotion JSON parse failed: {e}")

        # Clean up uploaded file
        try:
            genai.delete_file(image_file.name)
        except:
            pass

        if DEBUG_MODE:
            print(f"[DEBUG] Parsed - Type: {type_final}, Headline: {headline_final}, Desc: {description_final}, Keywords: {keywords_final}, Emotion: {emotion_final}")

        return type_final, headline_final, description_final, keywords_final, emotion_final

    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        return None, None, None, None, None

# --- Main Logic ---
def main():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    headline_rules, shotdesc_rules, keywords_rules = load_prompt_rules()
    if DEBUG_MODE:
        print(f"[DEBUG] Loaded rules - Headlines: {len(headline_rules)}, ShotDesc: {len(shotdesc_rules)}, Keywords: {len(keywords_rules)} chars")

    gemini_key = get_gemini_key(cursor)
    if not gemini_key:
        print("ERROR: Gemini API key not found.")
        return

    # Confirm target columns exist
    try:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'damz_test' AND TABLE_SCHEMA = 'dbo'
              AND COLUMN_NAME IN ('headline_type','headline_new','shot_description_new','keywords_new','emotion')
        """)
        cols = {row[0] for row in cursor.fetchall()}
        missing_cols = {'headline_type','headline_new','shot_description_new','keywords_new','emotion'} - cols
        if missing_cols:
            print(f"WARNING: Missing columns: {missing_cols}")
    except Exception as e:
        print(f"[DEBUG] Column check failed: {e}")

    # Pull records that need comprehensive processing
    cursor.execute(f"""
        SELECT TOP {1 if DEBUG_MODE else BATCH_LIMIT}
               fk_asset,
               headline,
               shot_description,
               keywords
        FROM docketwatch.dbo.damz_test
        WHERE headline IS NOT NULL and [version] = 2
          AND (headline_type IS NULL OR headline_new IS NULL OR shot_description_new IS NULL OR keywords_new IS NULL OR emotion IS NULL)
        ORDER BY fk_asset
    """)
    rows = cursor.fetchall()

    if DEBUG_MODE:
        print("[DEBUG MODE] Limiting to 1 record")

    print(f"Found {len(rows)} records to process")
    processed, skipped = 0, 0

    for fk_asset, headline, shot_description, keywords in rows:
        print(f"\nAsset: {fk_asset}")
        if DEBUG_MODE:
            print(f"[DEBUG] headline: {str(headline)[:100]}")
            print(f"[DEBUG] shot_description: {str(shot_description)[:100] if shot_description else 'None'}")
            print(f"[DEBUG] keywords: {str(keywords)[:100] if keywords else 'None'}")

        # Get image path
        image_path = get_image_path(cursor, fk_asset)
        if not image_path:
            print(f"SKIP: {fk_asset} (no image path found)")
            skipped += 1
            continue

        if DEBUG_MODE:
            print(f"[DEBUG] image_path: {image_path}")

        prompt = build_comprehensive_prompt(headline_rules, shotdesc_rules, keywords_rules, headline, shot_description, keywords)
        type_final, headline_final, description_final, keywords_final, emotion_final = analyze_comprehensive(prompt, image_path, gemini_key)

        if type_final and headline_final and description_final and keywords_final and emotion_final:
            # Update all fields
            cursor.execute("""
                UPDATE docketwatch.dbo.damz_test
                SET headline_type = ?,
                    headline_new = ?,
                    shot_description_new = ?,
                    keywords_new = ?,
                    emotion = ?
                WHERE fk_asset = ?
            """, (type_final, headline_final, description_final, keywords_final, emotion_final, fk_asset))
            conn.commit()

            print(f"OK: {fk_asset}")
            print(f"  Type: {type_final}")
            print(f"  Headline: {headline_final[:80]}...")
            print(f"  Description: {description_final[:80]}...")
            print(f"  Keywords: {keywords_final[:80]}...")
            print(f"  Emotion: {emotion_final}")
            processed += 1
        else:
            print(f"SKIP: {fk_asset} (incomplete processing)")
            skipped += 1

        time.sleep(SLEEP_SECONDS)

    print("\n=== BATCH COMPLETE ===")
    print(f"Processed: {processed}")
    print(f"Skipped:   {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
