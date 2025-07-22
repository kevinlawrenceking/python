<!--- Set API Call Master ID for 'Case Search' --->
<cfset api_call_master_id = 5>

<!--- Insert API Call into api_calls if it doesn't already exist --->
<cfquery datasource="Reach">
    INSERT INTO [docketwatch].[dbo].[api_calls] 
    ([fk_tool], [api_endpoint], [request_method], [request_params], [created_at], [name], [description], [fk_api_call_master])
    VALUES (
        <cfqueryparam value="1" cfsqltype="cf_sql_integer">,
        <cfqueryparam value="/caseSearch" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="GET" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="?q=caseNumber:%22##case_number##%22" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
        <cfqueryparam value="Case Search" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="Search for a case by case number" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#api_call_master_id#" cfsqltype="cf_sql_integer">
    )
</cfquery>

