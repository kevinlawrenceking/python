<cfparam name="url.status" default="Review">
<cfparam name="url.tool" default="">
<cfparam name="url.owner" default="">
<cfparam name="url.state" default="">
<cfparam name="url.county" default="">
<cfparam name="url.fk_celebrity" default="">

<cfquery name="getCourts" datasource="Reach">
WITH filtered_cases AS (
    SELECT co.court_code, co.court_name
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
    INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
    LEFT JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id  AND cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
    LEFT JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    WHERE c.status = <cfqueryparam value="#url.status#" cfsqltype="cf_sql_varchar">
   
    <cfif len(trim(url.tool))>
        AND c.fk_tool = <cfqueryparam value="#url.tool#" cfsqltype="cf_sql_integer">
    </cfif>
    <cfif len(trim(url.owner))>
        AND t.owners LIKE <cfqueryparam value="%#url.owner#%" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.state))>
        AND ct.state_code = <cfqueryparam value="#url.state#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.county))>
        AND co.fk_county = <cfqueryparam value="#url.county#" cfsqltype="cf_sql_integer">
    </cfif>
    <cfif len(trim(url.fk_celebrity))>
        AND cm.fk_celebrity = <cfqueryparam value="#url.fk_celebrity#" cfsqltype="cf_sql_integer">
    </cfif>
)
SELECT DISTINCT court_code, court_name
FROM filtered_cases
ORDER BY court_name
</cfquery>

<option value="">All Courthouses</option>
<cfoutput query="getCourts">
    <option value="#court_code#">#court_code# - #court_name#</option>
</cfoutput>
