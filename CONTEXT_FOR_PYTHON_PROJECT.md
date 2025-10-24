# Context: Dual Usage of Summarization Pipeline

## Summary for Python Project AI Assistant

**Date**: October 22, 2025  
**Integration Type**: Shared codebase serving two workflows

---

## Current State

The summarization pipeline (`summarize_document_event.py`) is now being used for **two different purposes**:

### 1. Original Usage (Existing System)
- **Purpose**: Process documents from case tracking/docket monitoring
- **Trigger**: Automated document ingestion from PACER/court systems  
- **Context**: Documents are part of tracked legal cases with existing case metadata
- **Integration**: Direct database integration, case event linking
- **Environment**: Server-side batch processing
- **Database**: Documents linked to real case events

### 2. New Usage (Upload Tool - Added Oct 2025)
- **Purpose**: Ad-hoc document analysis via web upload interface
- **Trigger**: Manual PDF upload through court-beta web interface at `/court-beta/tools/summarize/`
- **Context**: Standalone documents without case context ("Uploaded document for ad-hoc analysis")
- **Integration**: Called via CLI wrapper (`summarize_upload_cli.py`) from ColdFusion frontend
- **Environment**: Web-triggered, JSON response format
- **Database**: Documents linked to placeholder case event

---

## Key Integration Points

### CLI Wrapper
- **File**: `summarize_upload_cli.py`
- **Arguments**: 
  - `--in <file_path>` (required): Path to PDF file
  - `--extra <instructions>` (optional): Additional summarization instructions
- **Output**: Clean JSON to stdout (stderr used for logging)
- **Called By**: ColdFusion endpoint `ajax/upload_and_summarize.cfm`

### Shared Pipeline
Both workflows use identical processing:
- ✅ FACT_GUARD verification (extract → render → verify)
- ✅ OCR extraction (PyPDF2 + Tesseract fallback)
- ✅ AI summarization (Gemini API)
- ✅ Structured field extraction
- ✅ Same database connections (`get_cursor()`, `get_util()`)

### Database Integration
- **Original**: Documents inserted/updated for real case events
- **New (Ad-Hoc)**: Documents inserted with placeholder event ID
  - **Placeholder Event**: `E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6`
  - **Placeholder Case**: ADHOC-UPLOADS-2025 (case_id: 255815)
  - **Status**: "placeholder" (filtered out of normal tracking)

---

## Benefits of Shared Codebase

✅ **Single source of truth** for summarization logic  
✅ **Improvements benefit both systems** automatically  
✅ **Consistent output quality** and format  
✅ **No code duplication** or maintenance burden  
✅ **Same AI models** and verification pipeline  
✅ **Unified QC feedback** system for model improvements

---

## Recent Changes (Oct 22, 2025)

### Files Created in Python Project
1. **`summarize_upload_cli.py`** - CLI wrapper for web integration
   - Handles `--in` and `--extra` arguments
   - Redirects stdout to prevent JSON contamination
   - Returns structured JSON for ColdFusion consumption

2. **`ADHOC_UPLOAD_INTEGRATION.md`** - Integration documentation
   - Database setup instructions
   - Code changes needed for document persistence
   - Query examples for ad-hoc uploads

3. **`verify_summarize_upload_setup.py`** - Environment checker
   - Validates Python version, dependencies
   - Checks database connectivity
   - Verifies file paths and permissions

### Files Created in Court-Beta Project
1. **`/tools/summarize/index.cfm`** - Web upload interface
   - Drag-drop PDF upload
   - Processing status display
   - Results viewer with collapsible JSON
   - QC feedback form

2. **`/ajax/upload_and_summarize.cfm`** - Upload handler
   - File validation (PDF check, size limit)
   - SHA-256 hash computation
   - Python script execution via `cfexecute`
   - HTML comment filtering (fixes stdout contamination)
   - Document record update

3. **`/ajax/save_qc_feedback.cfm`** - QC persistence
   - Saves quality control feedback
   - Links via `doc_uid` or `upload_sha256`

4. **`/sql/adhoc_upload_setup.sql`** - Database setup
   - Creates placeholder case/event
   - Stored procedure for event ID lookup

5. **`/sql/create_summary_qc_feedback.sql`** - QC table
   - Tracks human feedback on summaries
   - Used for model improvement

---

## TODO: Python Project Changes

### Required Modifications to `summarize_upload_cli.py`

See `ADHOC_UPLOAD_INTEGRATION.md` for full details. Summary:

1. **Add constant**:
   ```python
   ADHOC_EVENT_ID = "E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6"
   ```

2. **Add import**:
   ```python
   import uuid
   ```

3. **Insert document record** (in `process_upload()` after OCR, before summarization):
   ```python
   doc_uid = str(uuid.uuid4()).upper()
   
   cur.execute("""
       INSERT INTO docketwatch.dbo.documents (
           doc_uid, fk_case_event, pdf_title, rel_path,
           created_at, updated_at, file_size, original_filename
       ) VALUES (?, ?, ?, ?, GETDATE(), GETDATE(), ?, ?)
   """, (
       doc_uid,
       ADHOC_EVENT_ID,
       f"Ad-Hoc Upload: {os.path.basename(file_path)}",
       f"uploads/{os.path.basename(file_path)}",
       os.path.getsize(file_path),
       os.path.basename(file_path)
   ))
   conn.commit()
   
   result["doc_uid"] = doc_uid
   ```

4. **Test**: Upload a PDF and verify:
   - Document record created in `documents` table
   - `doc_uid` returned in JSON
   - CFML successfully updates summary fields
   - QC feedback properly linked

---

## When Modifying Code

**Important**: Changes to core functions in `summarize_document_event.py` will affect **both workflows**:

- `extract_facts()` - Structured field extraction
- `render_summary()` - HTML summary generation  
- `verify_summary()` - FACT_GUARD verification
- `pdf_to_text()` - OCR processing
- `refine_ocr_with_ai()` - OCR improvement

**Test both workflows** when making significant changes:
1. Existing case document processing (automated)
2. Ad-hoc upload tool (manual web upload)

---

## Query Examples for Ad-Hoc Uploads

```sql
-- Get all ad-hoc uploads with summaries
SELECT 
    d.doc_uid,
    d.pdf_title,
    d.created_at,
    d.summary_ai_html,
    d.ai_processed_at
FROM docketwatch.dbo.documents d
JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
WHERE c.case_number = 'ADHOC-UPLOADS-2025'
ORDER BY d.created_at DESC;

-- Get uploads with QC feedback
SELECT 
    d.doc_uid,
    d.pdf_title,
    qc.success,
    qc.notes,
    qc.model_name,
    qc.created_at as qc_date
FROM docketwatch.dbo.documents d
JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
LEFT JOIN docketwatch.dbo.summary_qc_feedback qc ON qc.doc_uid = d.doc_uid
WHERE c.case_number = 'ADHOC-UPLOADS-2025'
  AND qc.id IS NOT NULL
ORDER BY qc.created_at DESC;
```

---

## Web Interface Location

**URL**: https://docketwatch.tmz.tv/court-beta/tools/summarize/

Users can:
1. Upload PDF documents (max 25 MB)
2. Add optional instructions
3. View AI-generated summary
4. Review OCR text and structured fields
5. Provide QC feedback (correct/incorrect, notes)

All results are now persisted to the database for analysis and improvement.

---

## Questions or Issues?

Contact the court-beta project for frontend/web interface issues.  
This Python project handles the core summarization logic and document processing.
