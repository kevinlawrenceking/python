# API Key Usage Audit - Python Scripts
**Date:** October 24, 2025

## ✅ PRODUCTION SCRIPTS - USING SERVICE ACCOUNT (CORRECT)

### ✅ `summarize_document_event.py` (Main Production Script)
- **Status:** MIXED - Imports service account helper but still retrieves API key
- **Line 23:** `from vertex_ai_helper import generate_content_vertex` ✅ Imports service account helper
- **Line 1175:** `key = get_util(cur, "gemini_api")` ❌ Still retrieves API key from database
- **Problem:** The script imports the service account helper but doesn't actually use it
- **Functions using API key:**
  - `get_available_model(api_key)` - Line 360
  - `extract_facts()` - Line 701
  - `render_summary()` - Line 805
  - `verify_summary()` - Line 832
  - `refine_ocr_with_ai()` - Line 1064
  - `ask_gemini()` - Line 1112
- **All these functions call:** `genai.configure(api_key=api_key)`

### ❌ `summarize_upload_cli.py` (Upload Tool)
- **Line 82:** `api_key = get_util(cur, "gemini_api")` - Retrieves API key from database
- **Status:** STILL USING API KEY
- **Passes API key to:** `extract_facts()`, `render_summary()`, `verify_summary()`, `refine_ocr_with_ai()`

## ❌ TEST/LEGACY SCRIPTS - STILL USING API KEYS

### ❌ `test_event_summary_fresh.py`
- **Line 6:** `import google.generativeai as genai`
- **Line 14:** `api_key = cursor.fetchone()[0]`
- **Line 18:** `genai.configure(api_key=api_key)`
- **Status:** Test script, still using API key

### ❌ `test_gemini_retry.py`
- **Line 9:** `def get_api_key()` - Retrieves from database
- **Line 39:** Uses API key in URL: `f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"`
- **Status:** Test script, uses REST API with key

### ❌ `pacer_case_event_pdf_summarizer.py`
- **Line 128:** `def summarize_case_html(html_text, api_key)`
- **Line 136:** Uses API key in URL for REST API calls
- **Status:** Legacy script, still using API key

### ❌ `summarize_case_event_ai.py`
- **Line 5:** `import google.generativeai as genai`
- **Line 15:** `cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")`
- **Line 21:** `genai.configure(api_key=row[0])`
- **Status:** Legacy script, still using API key

### ⚠️ `pacer_single.py`
- **Line 26:** `import google.generativeai as genai`
- **Status:** Unknown usage (need to check further)

### ⚠️ `clean_keywords.py`
- **Line 2:** `import google.generativeai as genai`
- **Status:** Unknown usage (need to check further)

### ⚠️ `test3.py`
- **Line 16:** `import google.generativeai as genai`
- **Status:** Test script, unknown usage

## ✅ SERVICE ACCOUNT INFRASTRUCTURE (CORRECT)

### ✅ `vertex_ai_helper.py`
- **Line 10:** `from google.oauth2 import service_account`
- **Line 18:** `SERVICE_ACCOUNT_FILE = os.path.join(SCRIPT_DIR, "docketwatch-service-account.json")`
- **Line 22-23:** `creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, ...)`
- **Status:** ✅ Properly configured service account helper

### ✅ `test_vertex_ai.py`
- **Line 7:** `from google.oauth2 import service_account`
- **Line 15:** `creds = service_account.Credentials.from_service_account_file(...)`
- **Status:** ✅ Test script using service account correctly

## ⚠️ OPENAI SCRIPTS (DIFFERENT SERVICE)

### `find_match.py`
- **Line 16:** `def get_openai_api_key(cursor)`
- **Line 115:** `openai.api_key = get_openai_api_key(cursor)`
- **Status:** This is OpenAI, not Google - different service (OK)

### `insert_court_from_url_final.py`
- **Line 30:** `openai.api_key = get_chatgpt_key()`
- **Status:** This is OpenAI, not Google - different service (OK)

---

## 🔴 CRITICAL FINDING

**Your main production script `summarize_document_event.py` is NOT using the service account!**

### Current State:
1. ✅ It imports `vertex_ai_helper` (Line 23)
2. ❌ It retrieves API key from database (Line 1175: `key = get_util(cur, "gemini_api")`)
3. ❌ All AI functions use `genai.configure(api_key=key)`
4. ❌ It never calls the service account helper functions

### The Problem:
The script has the service account infrastructure available but doesn't use it. All calls to Gemini still use the old API key method via `google.generativeai` library.

---

## 📋 RECOMMENDATION: REFACTOR NEEDED

### Scripts That MUST Be Updated:

1. **`summarize_document_event.py`** (HIGH PRIORITY - Production)
   - Remove `key = get_util(cur, "gemini_api")`
   - Replace all `genai.configure(api_key=...)` calls
   - Use `generate_content_vertex()` from `vertex_ai_helper` instead
   - Update all functions: `extract_facts()`, `render_summary()`, `verify_summary()`, `refine_ocr_with_ai()`, `ask_gemini()`

2. **`summarize_upload_cli.py`** (HIGH PRIORITY - Production)
   - Remove `api_key = get_util(cur, "gemini_api")`
   - Use service account methods instead

3. **`summarize_case_event_ai.py`** (MEDIUM - Legacy)
   - Update if still in use

4. **`pacer_case_event_pdf_summarizer.py`** (LOW - Legacy)
   - Update if still in use, otherwise archive

### Scripts That Can Stay As-Is (Test/Development):
- `test_event_summary_fresh.py` - Test script
- `test_gemini_retry.py` - Test script
- `test3.py` - Test script
- `pacer_single.py` - Check if in use
- `clean_keywords.py` - Check if in use

---

## ✅ CORRECT PATTERN (From vertex_ai_helper.py)

```python
# Initialize once at startup
import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project=PROJECT_ID, location=LOCATION)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(SERVICE_ACCOUNT_FILE)

# Then use directly (NO API KEY)
model = GenerativeModel("gemini-2.5-flash")
response = model.generate_content(...)
```

---

## SUMMARY

**STATUS: ❌ Main production scripts are STILL using API keys from the database**

The service account infrastructure exists (`vertex_ai_helper.py`) but **is not being used** by the main scripts. The import is there, but all the actual API calls still use the old `genai.configure(api_key=...)` pattern.

**Action Required:** Refactor `summarize_document_event.py` and `summarize_upload_cli.py` to use service account authentication instead of API keys.
