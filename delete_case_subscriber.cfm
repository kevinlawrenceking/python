<cfsetting enablecfoutputonly="true">
<cfcontent type="application/json; charset=utf-8">

<cftry>
    <cfparam name="url.id" type="numeric">

    <!--- Get the username before deleting so we can send it back --->
    <cfquery name="getUser" datasource="Reach">
        SELECT fk_username
        FROM docketwatch.dbo.case_email_recipients
        WHERE id = <cfqueryparam value="#url.id#" cfsqltype="cf_sql_integer">
    </cfquery>

    <cfif getUser.recordCount EQ 0>
        <cfoutput>
            {"success": false, "message": "Subscriber not found."}
        </cfoutput>
        <cfabort>
    </cfif>

    <cfset deletedUsername = getUser.fk_username>

    <!--- Delete the row --->
    <cfquery datasource="Reach">
       UPDATE docketwatch.dbo.case_email_recipients
       set notify = 0 
        WHERE id = <cfqueryparam value="#url.id#" cfsqltype="cf_sql_integer">
    </cfquery>

    <cfoutput>
        {
            "success": true,
            "message": "Subscriber removed successfully.",
            "fk_username": "#deletedUsername#"
        }
    </cfoutput>

<cfcatch>
    <cfoutput>
        {
            "success": false,
            "message": "#replace(cfcatch.message, '"', '\"', 'all')#"
        }
    </cfoutput>
</cfcatch>
</cftry>
