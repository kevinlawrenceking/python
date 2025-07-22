<cfsetting showdebugoutput="false">
<cfcontent type="application/json">
<cftry>
    <cfset requestData = DeserializeJSON(ToString(GetHttpRequestData().content))>

    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases
        SET status = <cfqueryparam value="#requestData.status#" cfsqltype="cf_sql_varchar">,
            last_updated = GETDATE()
        WHERE id = <cfqueryparam value="#requestData.id#" cfsqltype="cf_sql_integer">
    </cfquery>

    <cfoutput>#SerializeJSON({success: true})#</cfoutput>
    
    <cfcatch>
        <cfoutput>#SerializeJSON({success: false, message: cfcatch.message})#</cfoutput>
    </cfcatch>
</cftry>
