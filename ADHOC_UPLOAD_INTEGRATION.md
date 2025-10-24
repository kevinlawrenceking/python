# Ad-Hoc Upload Document Persistence

## Overview
Documents uploaded via the AI Summary Upload Tool are now persisted to the `documents` table using a placeholder case/event structure.

## Database Setup
**Placeholder Event ID**: `E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6`
- Case: ADHOC-UPLOADS-2025 (case_id: 255815)
- Event: "Ad-Hoc Document Upload"
- Status: "placeholder" (won't appear in normal tracking)

## Required Changes to `summarize_upload_cli.py`

### Step 1: Add constant at top of file
```python
# Placeholder event ID for ad-hoc uploads
ADHOC_EVENT_ID = "E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6"
```

### Step 2: Modify `process_upload()` function

Add this code **after extracting OCR text** (around line 95) and **before starting summarization**:

```python
# Create document record in database for this upload
doc_uid = str(uuid.uuid4()).upper()

cur.execute("""
    INSERT INTO docketwatch.dbo.documents (
        doc_uid,
        fk_case_event,
        pdf_title,
        rel_path,
        created_at,
        updated_at,
        file_size,
        original_filename
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

### Step 3: Add import at top
```python
import uuid
```

### Step 4: Update result initialization
Change line ~70 from:
```python
result = {
    "doc_uid": None,
    ...
}
```

To:
```python
result = {
    "doc_uid": None,  # Will be populated after document insert
    ...
}
```

## Flow After Changes

1. **User uploads PDF** → `/court-beta/tools/summarize/`
2. **CFML receives file** → `ajax/upload_and_summarize.cfm`
3. **Python CLI called** → `summarize_upload_cli.py --in <path>`
4. **Document inserted** → `documents` table with new `doc_uid`
5. **OCR + AI processing** → Summary generated
6. **Python returns JSON** → Including `doc_uid`
7. **CFML updates document** → Sets `summary_ai`, `summary_ai_html`, `ocr_text` using `doc_uid`
8. **QC feedback saved** → Can now link via `doc_uid` instead of just SHA-256

## Benefits

✅ Full historical log of all uploads  
✅ Can query documents table for ad-hoc uploads  
✅ QC feedback properly linked via `doc_uid`  
✅ Can build "Recent Uploads" feature later  
✅ Consistent with existing architecture  
✅ Won't pollute real case tracking (filtered by case_number)

## Query Examples

```sql
-- Get all ad-hoc uploads
SELECT d.*, ce.event_description
FROM docketwatch.dbo.documents d
JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
WHERE c.case_number = 'ADHOC-UPLOADS-2025'
ORDER BY d.created_at DESC;

-- Get uploads with QC feedback
SELECT 
    d.doc_uid,
    d.pdf_title,
    d.created_at,
    qc.success,
    qc.notes,
    qc.created_at as qc_date
FROM docketwatch.dbo.documents d
JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
LEFT JOIN docketwatch.dbo.summary_qc_feedback qc ON qc.doc_uid = d.doc_uid
WHERE c.case_number = 'ADHOC-UPLOADS-2025'
ORDER BY d.created_at DESC;

-- Count uploads by day
SELECT 
    CAST(d.created_at AS DATE) as upload_date,
    COUNT(*) as upload_count
FROM docketwatch.dbo.documents d
JOIN docketwatch.dbo.case_events ce ON d.fk_case_event = ce.id
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
WHERE c.case_number = 'ADHOC-UPLOADS-2025'
GROUP BY CAST(d.created_at AS DATE)
ORDER BY upload_date DESC;
```

## Next Steps for Python Project

1. Add the constant `ADHOC_EVENT_ID`
2. Add `import uuid` at top
3. Modify `process_upload()` to insert document record before processing
4. Ensure `doc_uid` is returned in JSON result
5. Test with sample upload to verify document is created

The CFML side is already set up to handle the `doc_uid` and update the document record with summary results.
