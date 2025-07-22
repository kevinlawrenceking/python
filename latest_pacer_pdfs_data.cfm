<cfcontent type="application/json" />
<cfset results = []>

<cfquery name="getPDFs" datasource="reach">
    SELECT TOP 100
        p.created_at,
        c.id AS case_id,
        c.case_number,
        c.case_name,
        e.event_date,
        p.pdf_title,
        p.local_pdf_filename
    FROM docketwatch.dbo.case_events_pdf p
    INNER JOIN docketwatch.dbo.case_events e ON p.fk_case_event = e.id
    INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
    WHERE p.local_pdf_filename IS NOT NULL and p.isDownloaded = 1 AND local_pdf_filename IS NOT NULL AND LEN(local_pdf_filename) > 0
    ORDER BY p.created_at DESC
</cfquery>

<cfloop query="getPDFs">
    <cfset struct = {
        formatted_created_at = dateFormat(getPDFs.created_at, "mm/dd/yyyy"),
        case_id = getPDFs.case_id,
        case_number = getPDFs.case_number,
        case_name = getPDFs.case_name,
        event_date = dateFormat(getPDFs.event_date, "yyyy-mm-dd"),
        pdf_title = getPDFs.pdf_title,
        local_pdf_filename = getPDFs.local_pdf_filename
    }>
    <cfset arrayAppend(results, struct)>
</cfloop>

<cfoutput>#serializeJSON(results)#</cfoutput>
