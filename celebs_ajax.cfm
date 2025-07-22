<cfparam name="url.status" default="Review">
<cfparam name="url.county" default="">
<cfparam name="url.tool" default="">

<cfquery name="filteredCases" datasource="reach">
    SELECT DISTINCT ce.name AS celebrity_name
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
    INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
    LEFT JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id AND cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
    LEFT JOIN docketwatch.dbo.celebrities ce ON ce.id = cm.fk_celebrity AND ce.name IS NOT NULL
    WHERE c.status = <cfqueryparam value="#url.status#" cfsqltype="cf_sql_varchar">
    <cfif len(trim(url.county))>
        AND ct.name = <cfqueryparam value="#url.county#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.tool))>
        AND c.fk_tool = <cfqueryparam value="#url.tool#" cfsqltype="cf_sql_integer">
    </cfif>
</cfquery>


<cfcontent type="application/json" reset="true">
<cfoutput>#serializeJSON(filteredCases)#</cfoutput>
