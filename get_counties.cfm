<cfparam name="url.status" default="Review">
<cfparam name="url.tool" default="">
<cfparam name="url.owner" default="">
<cfparam name="url.state" default="">
<cfparam name="url.courthouse" default="">
<cfparam name="url.fk_celebrity" default="">

<cfquery name="getCounties" datasource="Reach">
WITH filtered_cases AS (
    SELECT ct.id AS county_id, ct.name
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
    INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
    LEFT JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id AND cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
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
    <cfif len(trim(url.courthouse))>
        AND c.fk_court = <cfqueryparam value="#url.courthouse#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.fk_celebrity))>
        AND cm.fk_celebrity = <cfqueryparam value="#url.fk_celebrity#" cfsqltype="cf_sql_integer">
    </cfif>
)
SELECT DISTINCT county_id, name
FROM filtered_cases
ORDER BY name
</cfquery>

<option value="">All Counties</option>
<cfoutput>
<cfloop query="getCounties">
  <option value="#county_id#">#name#</option>
</cfloop>
</cfoutput>
