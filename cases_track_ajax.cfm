<Cfparam name="idlist" default="0"/>

<cfif idlist neq 0>
<cfquery name="remove" datasource="Reach">
update docketwatch.dbo.cases
set status = 'tracked' 
where id in (#idlist#)
</cfquery>
</cfif>


<cfcontent type="application/json">


<cfquery name="cases" datasource="Reach">
SELECT 
    c.id,
    c.case_number, 
    c.case_name, 
    c.notes, 
    c.last_updated,
    FORMAT(c.last_updated, 'MM-dd-yy hh:mm tt') AS formatted_last_updated,  
    co.court_name,
    c.case_type AS division,
    cm.fk_celebrity AS fk_celebrities,
               (
        SELECT STUFF((
            SELECT ', ' + ce.name
            FROM docketwatch.dbo.case_celebrity_matches cm
            JOIN docketwatch.dbo.celebrities ce ON ce.id = cm.fk_celebrity
            WHERE cm.fk_case = c.id
              AND cm.match_status <> 'Removed'
              AND ce.name IS NOT NULL
            FOR XML PATH(''), TYPE
        ).value('.', 'NVARCHAR(MAX)'), 1, 2, '')
    ) AS celebrity_name,
    ct.name AS county,
    cm.match_status,
    c.status
FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
LEFT JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id AND cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
LEFT JOIN docketwatch.dbo.celebrities ce ON ce.id = cm.fk_celebrity
WHERE c.status <> 'Removed'

ORDER BY c.id DESC
</cfquery>



<!--- Convert Query to JSON Array --->
<cfset data = []>

<cfloop query="cases">
    <cfset row = {
        "id": cases.id,
        "case_number": cases.case_number,
        "case_name": cases.case_name,
        "notes": cases.notes,
        "court_name": cases.court_name,
        "division": cases.division,   
        "last_updated": cases.last_updated,
        "possible_celebs": cases.celebrity_name,
        "fk_celebrities": cases.fk_celebrities,
        "county": cases.county,
        "status": cases.status
    }>

    <cfset arrayAppend(data, row)>
</cfloop>

<!--- Output JSON Response --->
<cfoutput>#serializeJSON(data)#</cfoutput>
