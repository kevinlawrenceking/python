<cfcontent type="application/json">
<cfset searchTerm = trim(lcase(url.term ?: form.term ?: ""))>

<cfif len(searchTerm) LT 2>
    <cfoutput>[]</cfoutput>
    <cfexit>
</cfif>

<cfquery name="qMatches" datasource="Reach">

SELECT top 20
    c.id AS celebrity_id,
    c.name AS celebrity_name,
    cn.name AS display_name,
    cn.isPrimary,
    CASE WHEN c.verified = 1 THEN 'Verified' ELSE '' END AS verified,
     CASE 
        WHEN cn.name = <cfqueryparam value="#searchTerm#" cfsqltype="cf_sql_varchar"> THEN 1
        ELSE 0
    END AS is_exact
FROM docketwatch.dbo.celebrity_names cn
JOIN docketwatch.dbo.celebrities c ON c.id = cn.fk_celebrity
WHERE cn.isDeleted = 0
  AND c.isDeleted = 0
  AND cn.name LIKE <cfqueryparam value="%#searchTerm#%" cfsqltype="cf_sql_varchar">
ORDER BY is_exact desc,cn.name
</cfquery>

       


<cfset results = []>

<cfloop query="qMatches">
    <cfset arrayAppend(results, {
        label = "#qMatches.display_name#",
        value = "#qMatches.display_name#",
        celebrity_id = "#qMatches.celebrity_id#",
        celebrity_name = "#qMatches.celebrity_name#",
        display_name = "#qMatches.display_name#",
        verified = "#qMatches.verified#",
        isPrimary = "#qMatches.isPrimary#"
    })>
</cfloop>

<cfoutput>#serializeJSON(results)#</cfoutput>
