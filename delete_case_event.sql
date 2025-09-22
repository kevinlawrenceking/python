-- Delete Case Event and Associated Data
-- Replace @case_event_id with the actual case event ID

DECLARE @case_event_id INT = 12345;  -- CHANGE THIS

-- Show what will be deleted (run this first)
SELECT 'CASE EVENT' AS type, ce.id, ce.event_no, ce.event_description, c.case_name
FROM docketwatch.dbo.case_events ce
JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
WHERE ce.id = @case_event_id

UNION ALL

SELECT 'DOCUMENT' AS type, d.doc_uid, d.pdf_title, d.rel_path, CAST(d.file_size AS NVARCHAR)
FROM docketwatch.dbo.documents d
WHERE d.fk_case_event = @case_event_id;

-- After confirming above results, run these DELETE statements:

-- 1. Delete documents first (due to foreign key)
DELETE FROM docketwatch.dbo.documents 
WHERE fk_case_event = @case_event_id;

-- 2. Delete case event
DELETE FROM docketwatch.dbo.case_events 
WHERE id = @case_event_id;

-- 3. Optional: Delete RSS entries for this event
-- (Only if you want to remove the RSS trigger record too)
/*
DELETE FROM docketwatch.dbo.rss_feed_entries 
WHERE pacer_id IN (
    SELECT pacer_id FROM docketwatch.dbo.cases c
    JOIN docketwatch.dbo.case_events ce ON c.id = ce.fk_cases
    WHERE ce.id = @case_event_id
) AND event_no = (
    SELECT event_no FROM docketwatch.dbo.case_events WHERE id = @case_event_id
);
*/

-- Verify deletion
SELECT 'Remaining case events' AS check_type, COUNT(*) AS count
FROM docketwatch.dbo.case_events 
WHERE id = @case_event_id

UNION ALL

SELECT 'Remaining documents' AS check_type, COUNT(*) AS count
FROM docketwatch.dbo.documents 
WHERE fk_case_event = @case_event_id;