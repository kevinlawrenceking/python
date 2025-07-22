<cfcontent type="application/json; charset=utf-8">

<cfquery name="getCaseEvents" datasource="reach">
    SELECT   
        c.id,
        ce.id as event_id,
          CONVERT(VARCHAR, ce.created_at, 126) as sortable_created_at,
          FORMAT(ce.created_at, 'MM-dd-yy hh:mm tt') AS formatted_created_at,
        c.case_number, 
        c.case_name, 
        ce.event_date, 
        ce.event_description
    FROM 
        docketwatch.dbo.case_events ce
    JOIN 
        docketwatch.dbo.cases c ON ce.fk_cases = c.id
    WHERE 
        ce.event_date >= '2025-01-01'
    ORDER BY 
        ce.id DESC
</cfquery>

<cfset result = []>
<cfloop query="getCaseEvents">
    <cfset arrayAppend(result, {
        id = getCaseEvents.id,
        event_id = getCaseEvents.event_id,
        sortable_created_at = getCaseEvents.sortable_created_at,
        formatted_created_at = getCaseEvents.formatted_created_at,
        case_number = getCaseEvents.case_number,
        case_name = getCaseEvents.case_name,
        event_date = dateFormat(getCaseEvents.event_date, "yyyy-mm-dd"),
        event_description = getCaseEvents.event_description
    })>
</cfloop>

<cfoutput>#serializeJSON(result)#</cfoutput>
