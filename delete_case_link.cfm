<cfcontent type="application/json">
<cftry>
    <cfset data = DeserializeJSON(ToString(getHttpRequestData().content))>
    <cfset linkId = data.id>

    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.case_links
        SET isActive = 0
        WHERE id = <cfqueryparam value="#linkId#" cfsqltype="cf_sql_integer">
    </cfquery>

    <cfoutput>
        {"success": true, "message": "Link deleted successfully."}
    </cfoutput>

<cfcatch>
    <cfoutput>
        {"success": false, "message": "#replace(cfcatch.message, '"', '', 'all')#"}
    </cfoutput>
</cfcatch>
</cftry>
