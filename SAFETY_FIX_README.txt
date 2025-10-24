"""
SAFETY FILTER FIX SUMMARY
========================

Problem:
--------
The upload tool was failing with "finish_reason is 2" errors when processing documents 
with sensitive content (e.g., assault allegations in the Sean Combs case). The error 
occurred because:

1. Google's Gemini AI has safety filters that block responses for content deemed 
   potentially harmful (harassment, hate speech, violence, etc.)
   
2. Legal documents legitimately discuss these topics as factual court records

3. The _response_to_text() function didn't check finish_reason before accessing 
   response.text, causing cryptic errors


Changes Made:
-------------

1. UPDATED _response_to_text() function (line ~361):
   - Now checks finish_reason BEFORE accessing response content
   - finish_reason values:
     * 1 = STOP (normal completion)
     * 2 = MAX_TOKENS (truncated due to length)
     * 3 = SAFETY (blocked by content filter)
     * 4 = RECITATION (blocked due to copyright)
     * 5 = OTHER
   
   - Provides informative error messages for blocked responses:
     * SAFETY: Lists which categories triggered (HARASSMENT, HATE_SPEECH, etc.)
     * RECITATION: Indicates copyright/recitation issues
     * MAX_TOKENS: Logs warning and continues (partial text may be usable)

2. ADDED SAFETY_SETTINGS configuration (line ~27):
   - New global constant with more permissive thresholds for legal documents
   - Set to "BLOCK_ONLY_HIGH" instead of default "BLOCK_MEDIUM_AND_ABOVE"
   - Applied to all 4 safety categories:
     * HARM_CATEGORY_HARASSMENT
     * HARM_CATEGORY_HATE_SPEECH  
     * HARM_CATEGORY_SEXUALLY_EXPLICIT
     * HARM_CATEGORY_DANGEROUS_CONTENT

3. UPDATED ALL API CALLS to include safety_settings parameter:
   - extract_facts() - line ~713
   - render_summary() - line ~809
   - verify_summary() - line ~837
   - refine_ocr_with_ai() - line ~1075 (two calls)
   - ask_gemini() - line ~1135


Expected Behavior After Fix:
----------------------------

SCENARIO A: Content passes with permissive settings
- Most legal documents will now process successfully
- The BLOCK_ONLY_HIGH threshold allows factual discussion of sensitive topics

SCENARIO B: Content still blocked (extreme cases)
- Document processing will fail gracefully with clear error message
- Error will indicate which safety categories triggered
- Message suggests adjusting safety_settings if needed
- Upload tool will receive informative JSON error response instead of crash


Testing:
--------
To test with a real document:
1. Use summarize_upload_cli.py with a sensitive document
2. Check that either:
   a) Document processes successfully (preferred outcome)
   b) Clear error message about safety filter (acceptable for extreme content)

Example error message format:
"LLM response blocked by safety filter. Categories: HARM_CATEGORY_HARASSMENT:HIGH. 
This may occur with sensitive legal content (e.g., assault allegations). 
Consider adjusting safety_settings."


Technical Notes:
----------------
- Safety settings are request-level, not account-level
- Different models may have different sensitivity thresholds
- Legal/factual content should generally pass with BLOCK_ONLY_HIGH setting
- If blocks persist, could lower further to BLOCK_NONE (use with caution)
- The fix maintains dual-purpose functionality (case tracking + upload tool)


Files Modified:
---------------
- summarize_document_event.py
  * _response_to_text() - enhanced error handling
  * SAFETY_SETTINGS - new global configuration
  * All generate_content() calls - added safety_settings parameter
"""
