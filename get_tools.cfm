<cfparam name="url.status" default="Review">
<cfparam name="url.tool" default="">
<cfparam name="url.owner" default="">
<cfparam name="url.state" default="">
<cfparam name="url.county" default="">
<cfparam name="url.courthouse" default="">
<cfparam name="url.fk_celebrity" default="">

<cfquery name="getTools" datasource="Reach">
    SELECT DISTINCT t.id, t.tool_name
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
    INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
    LEFT JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id AND cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
    WHERE 1 = 1
    
    <cfif len(trim(url.status))>
        AND c.status = <cfqueryparam value="#url.status#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.owner))>
        AND t.owners LIKE <cfqueryparam value="%#url.owner#%" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.state))>
        AND ct.state_code = <cfqueryparam value="#url.state#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.county))>
        AND ct.id = <cfqueryparam value="#url.county#" cfsqltype="cf_sql_integer">
    </cfif>
    <cfif len(trim(url.courthouse))>
        AND co.court_code = <cfqueryparam value="#url.courthouse#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.fk_celebrity))>
        AND cm.fk_celebrity = <cfqueryparam value="#url.fk_celebrity#" cfsqltype="cf_sql_char">
    </cfif>
    
</cfquery>

<option value="">All Tools</option>
<cfoutput query="getTools">
    <option value="#id#">#tool_name#</option>
</cfoutput>
