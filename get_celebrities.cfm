<cfparam name="url.status" default="Review">
<cfparam name="url.tool" default="">
<cfparam name="url.owner" default="">
<cfparam name="url.state" default="">
<cfparam name="url.county" default="">
<cfparam name="url.courthouse" default="">

<cfquery name="getCelebs" datasource="Reach">
    SELECT DISTINCT ce.id, ce.name as celebrity_name
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
    INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
    INNER JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id
    INNER JOIN docketwatch.dbo.celebrities ce ON ce.id = cm.fk_celebrity
    LEFT JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    WHERE cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">

    <cfif len(trim(url.status))>
        AND c.status = <cfqueryparam value="#url.status#" cfsqltype="cf_sql_varchar">
    </cfif>
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
        AND ct.id = <cfqueryparam value="#url.county#" cfsqltype="cf_sql_integer">
    </cfif>
    <cfif len(trim(url.courthouse))>
        AND co.court_code = <cfqueryparam value="#url.courthouse#" cfsqltype="cf_sql_varchar">
    </cfif>

    order by ce.name
</cfquery>

<option value="">All Celebrities</option>
  <option value="NONE">NO CELEBRITY</option>
<cfoutput query="getCelebs">
    <option value="#id#">#celebrity_name#</option>
</cfoutput>
