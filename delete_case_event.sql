-- Delete Case Event and Associated Data
-- Replace the GUID with your actual case event ID

-- STEP 1: Show what will be deleted (run this first to verify)
DECLARE @case_event_id UNIQUEIDENTIFIER = '6107341A-75EE-4673-A37C-ECBE8E2A5A44';  -- CHANGE THIS TO YOUR CASE EVENT GUID

SELECT 
    'CASE EVENT' AS type, 
    ce.id AS case_event_id,
    ce.event_no, 
    ce.event_description, 
    c.case_name,
    ce.status
FROM docketwatch.dbo.case_events ce
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
WHERE ce.id = @case_event_id

UNION ALL

SELECT 
    'DOCUMENT' AS type,
    CAST(d.doc_uid AS NVARCHAR) AS case_event_id,
    d.pdf_title AS event_no,
    d.rel_path AS event_description,
    CAST(d.file_size AS NVARCHAR) AS case_name,
    CASE WHEN d.rel_path IS NOT NULL THEN 'Has File Path' ELSE 'No File Path' END AS status
FROM docketwatch.dbo.documents d
WHERE d.fk_case_event = @case_event_id;

-- STEP 2: Delete statements (run after confirming above)
-- Since case_event_id is unique, these are simple direct deletes:

-- Delete documents first (foreign key constraint)
DELETE FROM docketwatch.dbo.documents 
WHERE fk_case_event = @case_event_id;

-- Delete the case event (unique ID)
DELETE FROM docketwatch.dbo.case_events 
WHERE id = @case_event_id;

-- STEP 3: Verify deletion (should return 0 for both)
SELECT 
    'Case Events Remaining' AS item,
    COUNT(*) AS count
FROM docketwatch.dbo.case_events 
WHERE id = @case_event_id

UNION ALL

SELECT 
    'Documents Remaining' AS item,
    COUNT(*) AS count
FROM docketwatch.dbo.documents 
WHERE fk_case_event = @case_event_id;

-- OPTIONAL: Delete RSS entries (only if you want to remove the original RSS trigger too)
/*
-- Get event details first
SELECT ce.event_no, c.pacer_id, c.case_name
FROM docketwatch.dbo.case_events ce
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
WHERE ce.id = @case_event_id;

-- Then delete RSS entry (if exists)
DELETE FROM docketwatch.dbo.rss_feed_entries 
WHERE pacer_id = [PACER_ID_FROM_ABOVE] 
  AND event_no = [EVENT_NO_FROM_ABOVE];
*/