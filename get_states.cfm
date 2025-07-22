<cfparam name="url.status" default="Review">
<cfparam name="url.tool" default="">
<cfparam name="url.owner" default="">
<cfparam name="url.county" default="">
<cfparam name="url.courthouse" default="">
<cfparam name="url.fk_celebrity" default="">

<cfquery name="getStates" datasource="Reach">
    SELECT DISTINCT s.state_code, s.state_name
    FROM docketwatch.dbo.states s
    INNER JOIN docketwatch.dbo.counties c ON c.state_code = s.state_code
    INNER JOIN docketwatch.dbo.courts co ON co.fk_county = c.id
    INNER JOIN docketwatch.dbo.cases ca ON ca.fk_court = co.court_code
    LEFT JOIN docketwatch.dbo.tools t ON t.id = ca.fk_tool
    LEFT JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = ca.id AND cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
    WHERE 1 = 1
    
    <cfif len(trim(url.status))>
        AND ca.status = <cfqueryparam value="#url.status#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.tool))>
        AND ca.fk_tool = <cfqueryparam value="#url.tool#" cfsqltype="cf_sql_integer">
    </cfif>
    <cfif len(trim(url.owner))>
        AND t.owners LIKE <cfqueryparam value="%#url.owner#%" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.county))>
        AND c.id = <cfqueryparam value="#url.county#" cfsqltype="cf_sql_integer">
    </cfif>
    <cfif len(trim(url.courthouse))>
        AND co.court_code = <cfqueryparam value="#url.courthouse#" cfsqltype="cf_sql_varchar">
    </cfif>
    <cfif len(trim(url.fk_celebrity))>
        AND cm.fk_celebrity = <cfqueryparam value="#url.fk_celebrity#" cfsqltype="cf_sql_integer">
    </cfif>
</cfquery>

<option value="">All States</option>
<cfoutput query="getStates">
    <option value="#state_code#">#state_name#</option>
</cfoutput>
