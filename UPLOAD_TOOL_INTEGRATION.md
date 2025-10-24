# Upload Tool Integration - ColdFusion Implementation Guide

## Overview

The Python summarization script (`summarize_upload_cli.py`) is working correctly and returns complete JSON data. **The missing piece is creating the database record in ColdFusion** after receiving the Python response.

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Python Processing | ✅ Working | Extracts text, generates summaries, returns JSON |
| JSON Response | ✅ Complete | All fields populated correctly |
| Database INSERT | ❌ **MISSING** | ColdFusion not creating document record |
| Structured Fields | ❌ Not Saved | Because no doc_uid exists to update |

## Problem

When you upload a document:
1. ✅ ColdFusion receives the file
2. ✅ ColdFusion calls Python: `python summarize_upload_cli.py --in <filepath>`
3. ✅ Python processes and returns complete JSON
4. ❌ **ColdFusion doesn't INSERT the document record**
5. ❌ Therefore, no document exists in the database

## Solution: ColdFusion Database Integration

### Ad-Hoc Container IDs

All uploaded documents use these shared IDs as a "parking spot":

```
Case ID:       255815
Case Event ID: E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6
```

These are reusable for ALL uploads - they're just containers, not real cases.

---

## Implementation Steps

### Step 1: Parse Python JSON Response

After calling the Python script, parse the JSON response:

```cfml
<cfset pythonCommand = "python u:\docketwatch\python\summarize_upload_cli.py --in #uploadedFilePath#">
<cfexecute name="python" arguments="#pythonCommand#" variable="pythonOutput" timeout="300" />
<cfset jsonResponse = deserializeJSON(pythonOutput)>
```

### Step 2: INSERT Document Record

Create the document record with the Python-generated data:

```cfml
<cfquery name="insertDoc" datasource="Docketwatch">
    INSERT INTO docketwatch.dbo.documents (
        fk_case,
        fk_case_event,
        pdf_title,
        rel_path,
        ocr_text,
        summary_ai,
        summary_ai_html,
        summary_ai_extraction_json,
        date_downloaded,
        ai_processed_at
    ) 
    OUTPUT INSERTED.doc_uid
    VALUES (
        255815,  /* Ad-hoc case ID */
        'E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6',  /* Ad-hoc event ID */
        <cfqueryparam value="#fileName#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#relativePath#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#jsonResponse.ocr_text#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#jsonResponse.summary_text#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#jsonResponse.summary_html#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#serializeJSON(jsonResponse.fields)#" cfsqltype="cf_sql_varchar" null="#!structKeyExists(jsonResponse, 'fields')#">,
        GETDATE(),
        GETDATE()
    )
</cfquery>

<cfset newDocUid = insertDoc.doc_uid>
```

### Step 3: Update Structured Fields

Populate the parsed summary fields:

```cfml
<cfif structKeyExists(jsonResponse, "fields")>
    <cfquery datasource="Docketwatch">
        UPDATE docketwatch.dbo.documents 
        SET 
            event_summary = <cfqueryparam value="#left(jsonResponse.fields.event_summary ?: '', 500)#" cfsqltype="cf_sql_varchar">,
            newsworthiness = <cfqueryparam value="#jsonResponse.fields.newsworthiness ?: ''#" cfsqltype="cf_sql_varchar">,
            newsworthiness_reason = <cfqueryparam value="#left(jsonResponse.fields.newsworthiness_reason ?: '', 200)#" cfsqltype="cf_sql_varchar">,
            story_headline = <cfqueryparam value="#left(jsonResponse.fields.story_headline ?: '', 200)#" cfsqltype="cf_sql_varchar">,
            story_sub_head = <cfqueryparam value="#left(jsonResponse.fields.story_sub_head ?: '', 300)#" cfsqltype="cf_sql_varchar">,
            story_body = <cfqueryparam value="#jsonResponse.fields.story_body ?: ''#" cfsqltype="cf_sql_varchar">,
            whats_next = <cfqueryparam value="#left(jsonResponse.fields.whats_next ?: '', 1000)#" cfsqltype="cf_sql_varchar">
        WHERE doc_uid = <cfqueryparam value="#newDocUid#" cfsqltype="cf_sql_uniqueidentifier">
    </cfquery>
</cfif>
```

### Step 4: Error Handling

Handle Python errors gracefully:

```cfml
<cfif structKeyExists(jsonResponse, "errors") AND arrayLen(jsonResponse.errors) GT 0>
    <!--- Log errors but still save what we got --->
    <cflog file="upload_errors" text="Doc #newDocUid#: #arrayToList(jsonResponse.errors, '; ')#">
    
    <!--- Set summary to error message if processing completely failed --->
    <cfif len(trim(jsonResponse.summary_html)) EQ 0>
        <cfquery datasource="Docketwatch">
            UPDATE docketwatch.dbo.documents 
            SET summary_ai_html = <cfqueryparam value="<p>Processing error: #jsonResponse.errors[1]#</p>" cfsqltype="cf_sql_varchar">
            WHERE doc_uid = <cfqueryparam value="#newDocUid#" cfsqltype="cf_sql_uniqueidentifier">
        </cfquery>
    </cfif>
</cfif>
```

---

## JSON Response Structure

The Python script returns this structure:

```json
{
  "doc_uid": null,
  "model_name": "gemini-2.5-flash",
  "summary_text": "Plain text version of summary",
  "summary_html": "<h3>EVENT SUMMARY</h3><p>...</p>...",
  "ocr_text": "Extracted text from PDF...",
  "fields": {
    "event_summary": "2-3 sentence summary of what happened",
    "newsworthiness": "yes|no",
    "newsworthiness_reason": "Why this is/isn't newsworthy",
    "story_headline": "Headline if newsworthy",
    "story_sub_head": "Subheadline if newsworthy",
    "story_body": "Full article body if newsworthy",
    "whats_next": "Next steps/deadlines mentioned",
    
    // Additional extraction fields if FACT_GUARD enabled:
    "doc_type": "motion|order|complaint|etc",
    "filing_date_iso": "2025-10-22",
    "parties": {
      "plaintiff": "Name",
      "defendant": "Name",
      "others": []
    },
    "filing_action_summary": "What action was taken",
    "requested_relief": ["Relief item 1", "Relief item 2"],
    "court_status": "Status of case",
    "orders": ["Order 1", "Order 2"],
    "statutes": ["18 USC 1591", "etc"],
    "counts_alleged": [1, 2, 3],
    "counts_convicted": [1, 3],
    "counts_dismissed": [2],
    "financial_terms": ["$100,000 fine"],
    "hearing_schedule": ["Hearing on 2025-11-15"],
    "next_actions": ["Response due by 2025-11-01"],
    "adjudication_mode": "plea_guilty|trial_guilty|unknown",
    "sentence": {
      "imprisonment_months": 24,
      "supervised_release_years": 3,
      "fine_usd": 100000,
      "restitution_usd": 50000
    },
    "protective_terms": ["No contact order"],
    "newsworthiness": "yes",
    "newsworthiness_reason": "Celebrity involvement",
    "confidence": "high|medium|low"
  },
  "verifier_result": "PASSED|FAILED",
  "verifier_notes": "Any verification issues",
  "errors": [],
  "processing_ms": 12345
}
```

---

## Field Truncation Limits

Apply these truncation limits when inserting structured fields:

| Field | Max Length | Notes |
|-------|-----------|-------|
| `event_summary` | 500 chars | Summary of document |
| `newsworthiness_reason` | 200 chars | Why newsworthy or not |
| `story_headline` | 200 chars | Article headline |
| `story_sub_head` | 300 chars | Article subheadline |
| `story_body` | No limit | Full article text |
| `whats_next` | 1000 chars | Next steps/deadlines |

Use `left()` function in ColdFusion to truncate:
```cfml
<cfset truncatedSummary = left(jsonResponse.fields.event_summary, 500)>
```

---

## Testing Checklist

After implementing the changes, verify:

- [ ] Upload a PDF document
- [ ] Python processing completes successfully
- [ ] Query the documents table for the new record:
  ```sql
  SELECT TOP 1 * 
  FROM docketwatch.dbo.documents 
  WHERE fk_case_event = 'E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6'
  ORDER BY date_downloaded DESC
  ```
- [ ] Verify these fields are populated:
  - [ ] `ocr_text` has content
  - [ ] `summary_ai_html` has content
  - [ ] `event_summary` has content
  - [ ] `newsworthiness` has value
  - [ ] `story_headline` has content
- [ ] Check for errors in `summary_ai_html` field
- [ ] View the document in the web interface

---

## File Location

The ColdFusion file to modify is likely in:
```
/court-beta/tools/summarize/
```

Look for the file that handles the upload form submission and calls the Python script.

---

## Support

If issues persist after implementation:

1. Check Python execution output for JSON validity
2. Verify the ad-hoc case event exists: `E906C250-7BBB-4D8E-BB1B-C5E1AB10BCE6`
3. Check SQL Server error logs for constraint violations
4. Verify file permissions on the uploaded PDF
5. Check Python log files in `u:\docketwatch\python\logs\`

---

## Additional Notes

### Why No doc_uid Parameter?

The Python script doesn't need a `doc_uid` parameter because:
1. It processes files that aren't in the database yet
2. It returns data for ColdFusion to INSERT
3. The upload tool flow is: File → Python → JSON → ColdFusion INSERT

### Event Summary Generation

The event-level summary (in `case_events.summarize`) won't generate until:
1. At least one document exists for the event
2. That document has an `event_summary` field populated
3. The document summarization process completes

For ad-hoc uploads, event summaries aren't critical since they're standalone documents.

### Article Table Integration

Optionally, after creating the document, you can also create an article record:
```sql
INSERT INTO docketwatch.dbo.articles (
    fk_case_event,
    headline,
    subheadline,
    body,
    newsworthiness,
    created_date
) VALUES (...)
```

This is Phase 4 functionality and not required for basic upload tool operation.
