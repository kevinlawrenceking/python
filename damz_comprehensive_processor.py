import pyodbc
import google.generativeai as genai
import re
import time
import os
import json

# --- CONFIG ---
BATCH_LIMIT = 100
MODEL_ID = 7                  # from dbo.gemini_models
TARGET_VERSION = 4            # new test version to insert (e.g., 3, 4, 5)
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

def load_prompt_rules():
    with open(PROMPT_RULES_PATH, "r", encoding="utf-8") as f:
        headline_rules = f.read()
    with open(PROMPT_SHOTDESC_PATH, "r", encoding="utf-8") as f:
        shotdesc_rules = f.read()
    with open(PROMPT_KEYWORDS_PATH, "r", encoding="utf-8") as f:
        keywords_rules = f.read()
    return headline_rules, shotdesc_rules, keywords_rules

def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api_damz FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

def get_gemini_model(cursor, model_id=7):
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
    words = s.split()
    if len(words) > 30:
        s = " ".join(words[:30])
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

def build_comprehensive_prompt(h_rules, sd_rules, kw_rules, headline, shot_description, keywords_raw):
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
Shot_Description: [clean, specific, <=30 words]
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
            image_file = genai.upload_file(path=image_path)
        except Exception as e:
            print(f"[ERROR] Upload failed {image_path}: {e}")
            return None, None, None, None, None

        resp = model.generate_content(
            [prompt, image_file],
            generation_config={"temperature": TEMPERATURE, "max_output_tokens": max_tokens}
        )
        text = (getattr(resp, "text", "") or "").strip()

        try:
            genai.delete_file(image_file.name)
        except:
            pass

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        type_final = headline_final = description_final = keywords_final = emotion_final = None

        for ln in lines:
            low = ln.lower()
            if low.startswith("type:"):
                v = ln.split(":", 1)[1].strip()
                type_final = v if v in VALID_TYPES else "Live Event"
            elif low.startswith("optimized_headline:"):
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
                    arr = json.loads(m.group())
                    if isinstance(arr, list):
                        cleaned = post_clean_keywords(arr)
                        if cleaned:
                            keywords_final = json.dumps(cleaned, separators=(",", ":"))
            elif low.startswith("emotion:"):
                v = ln.split(":", 1)[1].strip()
                m = re.search(r'\[.*\]', v, re.DOTALL)
                if m:
                    arr = json.loads(m.group())
                    if isinstance(arr, list):
                        cleaned = post_clean_emotions(arr)
                        if cleaned:
                            emotion_final = json.dumps(cleaned, separators=(",", ":"))

        return type_final, headline_final, description_final, keywords_final, emotion_final
    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        return None, None, None, None, None

def upsert_version_model(cursor, version, model_id):
    # record which model was used for this version
    cursor.execute("""
        MERGE dbo.damz_test_version_model AS t
        USING (SELECT ? AS version, ? AS fk_model) AS s
        ON t.version = s.version
        WHEN MATCHED THEN UPDATE SET fk_model = s.fk_model
        WHEN NOT MATCHED THEN INSERT (version, fk_model) VALUES (s.version, s.fk_model);
    """, (version, model_id))

def main():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    h_rules, sd_rules, kw_rules = load_prompt_rules()

    model_cfg = get_gemini_model(cursor, MODEL_ID)
    if not model_cfg["supports_vision"]:
        print("ERROR: Selected model does not support vision")
        return
    print(f"Using model: {model_cfg['display_name']} ({model_cfg['model_name']})")

    api_key = get_gemini_key(cursor)
    if not api_key:
        print("ERROR: Gemini API key not found")
        return

    # seed version-to-model mapping
    upsert_version_model(cursor, TARGET_VERSION, MODEL_ID)
    conn.commit()

    # pull version 0 baselines that do not yet have TARGET_VERSION
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
    """, (TARGET_VERSION,))
    rows = cursor.fetchall()

    print(f"Found {len(rows)} version 0 rows to process for version {TARGET_VERSION}")
    processed = skipped = 0

    for fk_asset, headline, shot_description, keywords in rows:
        print(f"\nAsset: {fk_asset}")

        image_path = get_image_path(cursor, fk_asset)
        if not image_path:
            print(f"SKIP: {fk_asset} (no image path)")
            skipped += 1
            continue

        prompt = build_comprehensive_prompt(h_rules, sd_rules, kw_rules, headline, shot_description, keywords)
        t_final, h_final, d_final, k_final, e_final =
            analyze_comprehensive(prompt, image_path, api_key, model_cfg["model_name"], model_cfg["max_tokens"])

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
            """, (h_final, d_final, t_final, k_final, TARGET_VERSION, e_final, fk_asset, TARGET_VERSION))
            conn.commit()

            print(f"OK: {fk_asset}")
            processed += 1
        else:
            print(f"SKIP: {fk_asset} (incomplete ai output)")
            skipped += 1

        time.sleep(SLEEP_SECONDS)

    print("\n=== BATCH COMPLETE ===")
    print(f"Processed: {processed}")
    print(f"Skipped:   {skipped}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
