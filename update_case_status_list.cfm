<cfsetting showdebugoutput="false">
<cfcontent type="application/json">

<cftry>
    <cfset requestData = DeserializeJSON(ToString(GetHttpRequestData().content))>
    <cfset idArray = ListToArray(requestData.idlist)>

    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases
        SET status = <cfqueryparam value="#requestData.status#" cfsqltype="cf_sql_varchar">,
            last_updated = GETDATE()
        WHERE id IN (<cfqueryparam value="#requestData.idlist#" cfsqltype="cf_sql_varchar" list="true">)
    </cfquery>

    <cfoutput>#SerializeJSON({success: true})#</cfoutput>

    <cfcatch>
        <cfoutput>#SerializeJSON({success: false, message: cfcatch.message})#</cfoutput>
    </cfcatch>
</cftry>
