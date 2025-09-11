-- Safe reset script for RSS testing
-- This will remove specific RSS entries and related records for re-testing

-- 1. Find the RSS entries you want to reset (replace with actual GUID/case info)
SELECT 
    rfe.guid,
    rfe.case_name,
    rfe.event_no,
    rfe.pacer_id,
    ce.id as case_event_id,
    ce.fk_cases
FROM docketwatch.dbo.rss_feed_entries rfe
LEFT JOIN docketwatch.dbo.case_events ce ON ce.fk_cases = (
    SELECT id FROM docketwatch.dbo.cases WHERE pacer_id = rfe.pacer_id
) AND ce.event_no = rfe.event_no
WHERE rfe.pub_date >= '2025-09-10'  -- Today's entries only
ORDER BY rfe.pub_date DESC;

-- 2. To reset a specific case's recent events (REPLACE 12345 with actual pacer_id):
/*
DECLARE @pacer_id INT = 12345;  -- Replace with target pacer_id
DECLARE @fk_case INT;

SELECT @fk_case = id FROM docketwatch.dbo.cases WHERE pacer_id = @pacer_id;

-- Delete documents created today for this case
DELETE FROM docketwatch.dbo.documents 
WHERE fk_case = @fk_case 
  AND CAST(date_downloaded AS DATE) = CAST(GETDATE() AS DATE);

-- Delete case_events created today for this case  
DELETE FROM docketwatch.dbo.case_events 
WHERE fk_cases = @fk_case 
  AND CAST(created_at AS DATE) = CAST(GETDATE() AS DATE);

-- Delete RSS entries for this case from today
DELETE FROM docketwatch.dbo.rss_feed_entries 
WHERE pacer_id = @pacer_id 
  AND CAST(pub_date AS DATE) = CAST(GETDATE() AS DATE);

PRINT 'Reset complete for pacer_id: ' + CAST(@pacer_id AS VARCHAR);
*/
