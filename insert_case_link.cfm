<cfcontent type="application/json">
<cftry>
    <cfset data = DeserializeJSON(ToString(getHttpRequestData().content))>

    <cfset fk_case = data.fk_case>
    <cfset fk_user = data.fk_user>
    <cfset case_url = trim(data.case_url)>
    <cfset category = "TMZ Story">
    <cfset title = "Untitled">

    <!--- Fetch title from URL --->
<cfhttp url="#case_url#" method="get" charset="utf-8" result="page">
    <cfhttpparam type="header" name="User-Agent" value="Mozilla/5.0">
</cfhttp>

<!--- Extract title using REFindNoCase with subExpressions --->
<cfset regex = "<title>(.*?)</title>">
<cfset title = "Untitled">

<cfset matchResult = REFindNoCase(regex, page.fileContent, 1, true)>
<cfif matchResult.len[1] GT 0>
    <cfset title = trim(mid(page.fileContent, matchResult.pos[2], matchResult.len[2]))>
    <cfif len(title) GT 100>
        <cfset title = left(title, 100)>
    </cfif>
</cfif>

<cfset title = HTMLEditFormat(title)>


    <!--- Insert into database --->
    <cfquery datasource="Reach">
        INSERT INTO docketwatch.dbo.case_links (
            fk_case, case_url, title, category, fk_user, created_at, isActive
        ) VALUES (
            <cfqueryparam value="#fk_case#" cfsqltype="cf_sql_integer">,
            <cfqueryparam value="#case_url#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#title#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#category#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#fk_user#" cfsqltype="cf_sql_varchar">,
            GETDATE(),
            1
        )
    </cfquery>

<cfoutput>
    {
        "success": true,
        "message": "Link added",
        "title": "#htmlEditFormat(title)#",
        "redirect": "yes"
    }
</cfoutput>
<cfcatch>
    <cfoutput>
        {"success": false, "message": "#replace(cfcatch.message, '"', '', 'all')#"}
    </cfoutput>
</cfcatch>
</cftry>
