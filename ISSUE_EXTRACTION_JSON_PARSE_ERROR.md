# Issue: Extraction JSON Parse Error in Ad-Hoc Upload Tool

**Date**: October 22, 2025  
**Severity**: High - Blocking ad-hoc upload functionality  
**Component**: `summarize_document_event.py` - `extract_facts()` function  

---

## Problem Description

The ad-hoc upload tool is failing during the **extraction phase** when processing certain PDF documents. The AI (Gemini) is returning malformed JSON that cannot be parsed, causing the entire summarization pipeline to fail.

### Error Message
```
ValueError: Extraction JSON parse failed: Expecting ',' delimiter: line 75 column 82 (char 3599)
```

### Error Preview
The partial JSON before failure:
```json
{
  "doc_type": "Order",
  "filing_date_iso": "2025-09-08",
  "parties": {
    "plaintiff": "Anna Kane",
    "defendant": "Sean Combs, et al.",
    "others": []
  },
  "filing_action_summary": "Defendants Sean Combs and Harve Pierre filed a letter motion seeking a stay of discovery pending two appeals. The court held a conference and directed plaintiff's counsel to file a proposal for limited fact…
```

**Note**: The JSON is truncated at position 3599, suggesting the AI response was cut off mid-field.

---

## Root Causes

### 1. **Token Limit Exceeded**
- The Gemini API may be hitting the max token limit during extraction
- JSON is being truncated mid-response
- Incomplete objects/arrays cannot be parsed

### 2. **Unescaped Special Characters**
- Document text may contain characters that break JSON (quotes, backslashes, control chars)
- AI is not properly escaping these in the JSON output
- Parser fails when encountering invalid characters

### 3. **AI Model Hallucination**
- Model occasionally generates syntactically invalid JSON
- Missing commas, brackets, or quotes
- Malformed array/object structures

---

## Impact

### User Experience
- ❌ Upload fails completely
- ❌ No summary generated
- ❌ OCR text is extracted but unusable
- ❌ No structured fields available

### System Impact
- Affects **ad-hoc uploads** via web interface (`/court-beta/tools/summarize/`)
- May also affect **automated document processing** if same extraction logic is used
- Blocks QC feedback collection for affected documents

---

## Where to Fix

### Primary Location
**File**: `summarize_document_event.py`  
**Function**: `extract_facts()`  
**Line**: Wherever the extraction JSON is parsed (likely `json.loads(response.text)`)

### Current Flow (Suspected)
```python
def extract_facts(ocr_text, case_overview, event_desc, event_date, api_key):
    # 1. Build prompt for extraction
    prompt = build_extraction_prompt(ocr_text, ...)
    
    # 2. Call Gemini API
    response = gemini_api_call(prompt, api_key)
    
    # 3. Parse JSON (THIS IS WHERE IT FAILS)
    extraction = json.loads(response.text)  # ← ERROR HERE
    
    return raw_response, extraction
```

---

## Recommended Solutions

### Solution 1: Increase Token Limit (Quick Fix)
```python
# In Gemini API call configuration
generation_config = {
    "max_output_tokens": 8192,  # Increase from default (usually 2048)
    "temperature": 0.1,
    "response_mime_type": "application/json"
}
```

**Pros**: Simple, may prevent truncation  
**Cons**: Doesn't fix underlying malformed JSON issue

---

### Solution 2: Add JSON Repair/Validation (Recommended)
```python
import json
import re

def parse_extraction_json(response_text):
    """
    Safely parse extraction JSON with repair attempts.
    """
    try:
        # First attempt: direct parse
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}", file=sys.stderr)
        
        # Attempt 1: Fix truncated JSON
        try:
            # Find last complete object/array
            truncated = response_text[:e.pos]  # Get valid portion
            # Try to close unclosed structures
            repaired = auto_close_json(truncated)
            return json.loads(repaired)
        except:
            pass
        
        # Attempt 2: Extract JSON from markdown code blocks
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except:
            pass
        
        # Attempt 3: Use regex to extract fields manually
        try:
            return extract_fields_with_regex(response_text)
        except:
            pass
        
        # All attempts failed
        raise ValueError(
            f"Extraction JSON parse failed: {e}. "
            f"Preview: {response_text[:500]}"
        )

def auto_close_json(truncated_json):
    """
    Attempt to close unclosed JSON structures.
    """
    # Count unclosed brackets/braces
    open_braces = truncated_json.count('{') - truncated_json.count('}')
    open_brackets = truncated_json.count('[') - truncated_json.count(']')
    open_quotes = truncated_json.count('"') % 2
    
    # Close structures
    if open_quotes:
        truncated_json += '"'
    
    truncated_json += ']' * open_brackets
    truncated_json += '}' * open_braces
    
    return truncated_json
```

**Pros**: Handles multiple failure modes, more robust  
**Cons**: More complex implementation

---

### Solution 3: Add Retry Logic with Backoff
```python
import time

def extract_facts_with_retry(ocr_text, case_overview, event_desc, event_date, api_key, max_retries=3):
    """
    Extract facts with exponential backoff retry.
    """
    for attempt in range(max_retries):
        try:
            return extract_facts(ocr_text, case_overview, event_desc, event_date, api_key)
        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                # Last attempt failed
                raise ValueError(f"Extraction JSON parse failed after {max_retries} attempts: {e}")
            
            # Wait before retry (exponential backoff)
            wait_time = 2 ** attempt
            print(f"Extraction failed (attempt {attempt + 1}), retrying in {wait_time}s...", file=sys.stderr)
            time.sleep(wait_time)
```

**Pros**: Handles transient failures, simple to implement  
**Cons**: Doesn't fix malformed JSON, just retries

---

### Solution 4: Improve Prompt Engineering (Long-term)
```python
# Add explicit JSON formatting instructions to prompt
extraction_prompt = f"""
CRITICAL: Your response MUST be valid JSON. Follow these rules:
1. Always close all braces, brackets, and quotes
2. Escape special characters (quotes, backslashes)
3. Use null for missing values, not omit fields
4. Do not truncate - if running out of tokens, summarize remaining content

Extract the following fields from this legal document:
...

RESPOND WITH VALID JSON ONLY. NO MARKDOWN. NO EXPLANATIONS.
"""
```

**Pros**: Prevents issue at source  
**Cons**: AI may still make mistakes

---

### Solution 5: Switch to Structured Output Mode (Best)
```python
# Use Gemini's structured output feature (if available)
schema = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string"},
        "filing_date_iso": {"type": "string"},
        "parties": {
            "type": "object",
            "properties": {
                "plaintiff": {"type": "string"},
                "defendant": {"type": "string"},
                "others": {"type": "array", "items": {"type": "string"}}
            }
        },
        # ... rest of schema
    },
    "required": ["doc_type", "parties"]
}

response = model.generate_content(
    prompt,
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": schema  # Force valid JSON output
    }
)
```

**Pros**: Guarantees valid JSON structure  
**Cons**: Requires schema definition, may not support all Gemini versions

---

## Recommended Implementation Plan

### Phase 1: Immediate (Fix Blocking Issue)
1. ✅ **Increase `max_output_tokens`** to 8192 in extraction API call
2. ✅ **Add try/except** around JSON parsing with detailed error logging
3. ✅ **Return partial data** when extraction fails (OCR text still useful)

### Phase 2: Short-term (Improve Robustness)
4. ✅ **Implement JSON repair logic** (auto-close truncated JSON)
5. ✅ **Add retry mechanism** with exponential backoff (max 3 attempts)
6. ✅ **Better error messages** - Include problematic JSON in error output

### Phase 3: Long-term (Prevent Future Issues)
7. ✅ **Define JSON schema** for structured output mode
8. ✅ **Improve prompt engineering** with explicit JSON formatting rules
9. ✅ **Add validation** - Verify extracted fields before returning
10. ✅ **Monitor metrics** - Track extraction failure rate

---

## Example Code Changes

### In `extract_facts()` function:
```python
def extract_facts(ocr_text, case_overview, event_desc, event_date, api_key):
    """
    Extract structured facts from document text using AI.
    """
    # Build extraction prompt
    prompt = build_extraction_prompt(ocr_text, case_overview, event_desc, event_date)
    
    # Call Gemini API with increased token limit
    response = model.generate_content(
        prompt,
        generation_config={
            "max_output_tokens": 8192,  # INCREASED FROM DEFAULT
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    )
    
    raw_response = response.text
    
    # Parse JSON with error handling
    try:
        extraction = json.loads(raw_response)
    except json.JSONDecodeError as e:
        # Log detailed error
        print(f"JSON parse error at position {e.pos}: {e.msg}", file=sys.stderr)
        print(f"Problematic JSON preview: {raw_response[:500]}...", file=sys.stderr)
        
        # Attempt repair
        try:
            repaired = auto_close_json(raw_response[:e.pos])
            extraction = json.loads(repaired)
            print("JSON repair successful", file=sys.stderr)
        except Exception as repair_err:
            raise ValueError(
                f"Extraction JSON parse failed: {e}. "
                f"Repair attempt also failed: {repair_err}. "
                f"Preview: {raw_response[:500]}"
            )
    
    return raw_response, extraction
```

---

## Testing

### Test Cases Needed
1. **Large documents** (>10 pages) that may hit token limits
2. **Documents with special characters** (quotes, backslashes, unicode)
3. **Complex legal language** with nested clauses
4. **Documents that previously failed** (Anna Kane case mentioned in error)

### Success Criteria
- ✅ Extraction succeeds for 95%+ of documents
- ✅ Graceful degradation when extraction fails (OCR still available)
- ✅ Clear error messages for debugging
- ✅ No silent failures

---

## Related Files

### Files to Modify (Python Project)
- `summarize_document_event.py` - Main extraction logic
- `summarize_upload_cli.py` - CLI wrapper (may need error handling updates)

### Files Already Updated (Court-Beta Project)
- ✅ `/tools/summarize/index.cfm` - Now displays `data.errors` array gracefully
- ✅ `/ajax/upload_and_summarize.cfm` - Improved error logging

---

## Current Workaround (Court-Beta Side)

The frontend now handles extraction errors gracefully:
- Shows warning alert with error details
- Still displays OCR text for manual review
- Still displays raw JSON response for debugging
- Allows QC feedback submission (even for failed extractions)

**However**, this is just error handling - the **root cause must be fixed in Python** to restore full functionality.

---

## Questions for Investigation

1. What is the current `max_output_tokens` setting in extraction API calls?
2. Is `response_mime_type: "application/json"` being used?
3. Are there any existing JSON validation/repair utilities?
4. What percentage of documents are failing? (Need metrics)
5. Is the same extraction logic used for automated processing? (May affect more than just uploads)

---

## Contact

**Issue Reporter**: Court-Beta project  
**Affected Component**: Ad-hoc upload tool at `/court-beta/tools/summarize/`  
**Test URL**: https://docketwatch.tmz.tv/court-beta/tools/summarize/  
**Priority**: High - Users cannot complete uploads successfully
