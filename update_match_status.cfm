<cfparam name="form.id" type="integer">
<cfparam name="form.status" type="string">

<cfquery datasource="reach">
    UPDATE docketwatch.dbo.case_celebrity_matches
    SET match_status = <cfqueryparam value="#form.status#" cfsqltype="cf_sql_varchar">
    WHERE id = <cfqueryparam value="#form.id#" cfsqltype="cf_sql_integer">
</cfquery>

<cfoutput>{"success": true}</cfoutput>
