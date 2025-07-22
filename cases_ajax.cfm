<Cfparam name="idlist" default="0"/>
<cfparam name="url.status" default="Review">
<cfparam name="url.county" default="">
<cfparam name="url.owner" default="">
<cfparam name="url.state" default="">
<cfparam name="url.courthouse" default="">
<cfparam name="url.celebrity" default="">
<cfparam name="url.tool" default="">
<cfif idlist neq 0>

    <cfquery name="remove" datasource="Reach">
    update docketwatch.dbo.cases
    set status = 'Removed' 
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
    c.last_found as last_updated,
    CONVERT(VARCHAR, c.last_found, 126) AS sortable_last_updated,
    FORMAT(c.last_found, 'MM-dd-yy hh:mm tt') AS formatted_last_updated,

    c.created_at,
    CONVERT(VARCHAR, c.created_at, 126) AS sortable_created_at,
    FORMAT(c.created_at, 'MM-dd-yy hh:mm tt') AS formatted_created_at,
    co.court_name,
    c.case_type AS division,
    c.courtCaseNumber,
    celeb_data.fk_celebrity,
    celeb_data.celebrity_name,
    celeb_data.case_keywords,
    ct.id AS county_id,
    ct.name AS county,
    c.not_found_count,
    'http://#application.serverDomain#/docs/cases/' + cast(c.id AS VARCHAR) + '/E' + cast(c.courtCaseNumber AS VARCHAR) + '.pdf' AS pdfFilePath,
    cd.id as case_doc_id,
    c.status,
    'case_details.cfm?id=' + CAST(c.id AS VARCHAR) AS internal_case_url,
    c.case_url AS external_case_url,
    c.fk_tool,
    t.owners,
    t.tool_name,
    cp.name as priority

FROM docketwatch.dbo.cases c
LEFT JOIN docketwatch.dbo.case_documents cd on cd.fk_case = c.id
LEFT JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
LEFT JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
LEFT JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
LEFT JOIN docketwatch.dbo.case_priority cp ON cp.id = c.fk_priority
-- Subquery joins to only one row per case
LEFT JOIN (
    SELECT 
        cm.fk_case,
        MAX(cm.fk_celebrity) AS fk_celebrity,
        MAX(CAST(ce.case_keywords AS INT)) AS case_keywords,
        STUFF((
            SELECT ', ' + ce2.name
            FROM docketwatch.dbo.case_celebrity_matches cm2
            JOIN docketwatch.dbo.celebrities ce2 ON ce2.id = cm2.fk_celebrity
            WHERE cm2.fk_case = cm.fk_case
              AND cm2.match_status <> 'Removed'
              AND ce2.name IS NOT NULL
            FOR XML PATH(''), TYPE
        ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS celebrity_name
    FROM docketwatch.dbo.case_celebrity_matches cm
    JOIN docketwatch.dbo.celebrities ce ON ce.id = cm.fk_celebrity
    WHERE cm.match_status <> 'Removed'
    GROUP BY cm.fk_case
) celeb_data ON celeb_data.fk_case = c.id


WHERE c.status = <cfqueryparam value="#url.status#" cfsqltype="cf_sql_varchar">

<cfif len(trim(url.celebrity))>

<cfif trim(url.celebrity) eq "NONE">
AND celeb_data.fk_celebrity is NULL
<cfelse>
    AND celeb_data.fk_celebrity = <cfqueryparam value="#url.celebrity#" cfsqltype="cf_sql_char">
    </cfif>
</cfif>

<cfif structKeyExists(url, "docsearch") AND len(trim(url.docsearch))>
    AND cd.ocr_text LIKE <cfqueryparam value="%#url.docsearch#%" cfsqltype="cf_sql_varchar">
</cfif>
 
<cfif len(trim(url.tool))>
    AND c.fk_tool = <cfqueryparam value="#url.tool#" cfsqltype="cf_sql_integer">
</cfif>

<cfif len(trim(url.county))>
    AND co.fk_county = <cfqueryparam value="#url.county#" cfsqltype="cf_sql_integer">
</cfif>

<cfif len(trim(url.owner))>
    AND t.owners LIKE <cfqueryparam value="%#url.owner#%" cfsqltype="cf_sql_varchar">
</cfif>

<cfif len(trim(url.state))>
    AND ct.state_code = <cfqueryparam value="#url.state#" cfsqltype="cf_sql_varchar">
</cfif>

<cfif len(trim(url.courthouse))>
    AND c.fk_court = <cfqueryparam value="#url.courthouse#" cfsqltype="cf_sql_varchar">
</cfif>

</cfquery>


<!--- Convert Query to JSON Array --->
<cfset data = []>

<cfloop query="cases">
    <!--- Check if PDF file exists using environment-aware path --->
    <cfset pdfFilePath = "#application.fileSharePath#\docs\cases\" & cases.id & "\E" & cases.courtCaseNumber & ".pdf">
    <cfset pdfExists = fileExists(pdfFilePath)>
    
    <cfset row = {
        "id": cases.id,
        "case_number": cases.case_number,
        "case_name": cases.case_name,
        "notes": cases.notes,
        "court_name": cases.court_name,
        "priority": cases.priority,   
        "last_updated": cases.last_updated,
        "formatted_last_updated": cases.formatted_last_updated,
        "sortable_last_updated": cases.sortable_last_updated,
        "created_at": cases.created_at,
        "formatted_created_at": cases.formatted_created_at,
        "sortable_created_at": cases.sortable_created_at,
        "possible_celebs": cases.celebrity_name,
        "fk_celebrities": cases.fk_celebrity,
        "county": cases.county,
        "status": cases.status,
        "internal_case_url": cases.internal_case_url,
        "external_case_url": cases.external_case_url,
        "pdf_link": pdfExists ? cases.pdfFilePath : "",
        "case_keywords": cases.case_keywords,
        "tool_name": cases.tool_name,
        "not_found_count": cases.not_found_count
    }>

    <cfset arrayAppend(data, row)>
</cfloop>

<!--- Output JSON Response --->
<cfoutput>#serializeJSON(data)#</cfoutput>
