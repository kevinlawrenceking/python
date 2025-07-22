<cfquery name="casesWithoutToolCase" datasource="Reach">
    SELECT c.id, t.api_key, c.tool_case_id, ac.request_method, ac.api_endpoint, t.api_base_url
    FROM docketwatch.dbo.tool_cases c
    INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    INNER JOIN docketwatch.dbo.api_calls ac ON ac.fk_tool = t.id
    WHERE ac.fk_api_call_master = 4 AND c.is_tracked = 0;
</cfquery>

<cfloop query="casesWithoutToolCase">
    <cfset id = casesWithoutToolCase.id>
    <cfset tool_case_id = casesWithoutToolCase.tool_case_id>
    <cfset api_key = casesWithoutToolCase.api_key>
    <cfset request_method = casesWithoutToolCase.request_method>
    <cfset api_endpoint = casesWithoutToolCase.api_endpoint>
      <cfset api_base_url = casesWithoutToolCase.api_base_url>

    <!--- Construct API URL --->
    <cfset api_url = api_base_url & api_endpoint>

    <!--- Create JSON Body --->
    <cfset request_body = '{
 
            "caseId": "' & tool_case_id & '"
        }'>


    <!--- Debugging Output (Can be removed in production) --->
    <cfoutput>
        <p>Making API Call: #api_url#</p>
        <p>Request Method: #request_method#</p>
        <p>Request Body: #request_body#</p>
    </cfoutput>

    <!--- Make API Call --->
    <cfhttp url="#api_url#" method="#request_method#" result="apiResponse">
        <cfhttpparam type="header" name="Authorization" value="Bearer #api_key#">
        <cfhttpparam type="header" name="Content-Type" value="application/json">
        <cfhttpparam type="body" value="#request_body#">
    </cfhttp>

    <!--- Check API Response --->
    <cfif apiResponse.statusCode EQ "200">
        <!--- Update tool_cases to mark as tracked --->
        <cfquery datasource="Reach">
            UPDATE docketwatch.dbo.tool_cases
            SET is_tracked = 1
            WHERE tool_case_id = <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">
        </cfquery>

        <!--- Insert new tracking record into tool_alerts --->
        <cfquery datasource="Reach">
            INSERT INTO docketwatch.dbo.tool_alerts
            (fk_tool_case, schedule_type, last_track_date, last_fetch_date, last_fetch_date_with_updates, case_api, created_at)
            VALUES (
                <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="daily" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                <cfqueryparam value=NULL cfsqltype="cf_sql_varchar" null="true">,
                <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">
            )
        </cfquery>

        <cfoutput>
            <p>Case #tool_case_id# successfully tracked and updated in the database.</p>
        </cfoutput>
    <cfelse>
        <cfoutput>
            <p>Failed to track case #tool_case_id#. API Response: #apiResponse.fileContent#</p>
        </cfoutput>
    </cfif>
</cfloop>
