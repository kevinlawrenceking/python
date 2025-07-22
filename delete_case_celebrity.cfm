<cfcontent type="application/json">
<cftry>
    <!--- Parse JSON input --->
    <cfset data = DeserializeJSON(ToString(getHttpRequestData().content))>
    <cfset matchId = data.id>

    <!--- Soft delete the match by updating match_status --->
    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.case_celebrity_matches
        SET match_status = 'Removed'
        WHERE id = <cfqueryparam value="#matchId#" cfsqltype="cf_sql_varchar">
    </cfquery>

    <cfoutput>
        {"success": true, "message": "Celebrity match removed successfully."}
    </cfoutput>

<cfcatch>
    <cfoutput>
        {"success": false, "message": "#replace(cfcatch.message, '\"', '', 'all')#"}
    </cfoutput>
</cfcatch>
</cftry>
