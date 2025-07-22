 
<!--- Query case updates that need to be checked --->
<cfquery name="pendingUpdates" datasource="Reach">
    SELECT cul.fk_tool_case, t.api_key
    FROM docketwatch.dbo.case_update_log cul
    INNER JOIN docketwatch.dbo.tools t 
        ON t.id = (SELECT fk_tool FROM docketwatch.dbo.tool_cases WHERE tool_case_id = cul.fk_tool_case)
    WHERE cul.update_status IN ('IN_PROGRESS', 'COMPLETE');
</cfquery>


<cfloop query="pendingUpdates">
    <cfset tool_case_id = pendingUpdates.fk_tool_case>
    <cfset api_key = pendingUpdates.api_key>

    <!--- Construct API URL for checking case update status --->
    <cfset api_url = "https://enterpriseapi.unicourt.com/caseUpdate/" & tool_case_id>

    <!--- Make API Call --->
    <cfhttp url="#api_url#" method="GET" result="apiResponse">
        <cfhttpparam type="header" name="Authorization" value="Bearer #api_key#">
    </cfhttp>

    <!--- Parse API Response --->
    <cfset jsonResponse = DeserializeJSON(apiResponse.fileContent)>

<cfif StructKeyExists(jsonResponse, "status") AND jsonResponse.status EQ "COMPLETE">
    <!--- Retrieve the last stored update response for this case --->
    <cfquery name="lastUpdate" datasource="Reach">
        SELECT TOP 1 update_response 
        FROM docketwatch.dbo.case_update_log 
        WHERE fk_tool_case = <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">
        ORDER BY update_completed DESC;
    </cfquery>

    <cfset newUpdateResponse = apiResponse.fileContent>
    <cfset lastUpdateResponse = "">

    <cfif lastUpdate.recordCount GT 0>
        <cfset lastUpdateResponse = lastUpdate.update_response>
    </cfif>

    <!--- Only proceed if the update response is different --->
    <cfif newUpdateResponse NEQ lastUpdateResponse>
        <!--- Update case_update_log with the new response --->
        <cfquery datasource="Reach">
            UPDATE docketwatch.dbo.case_update_log 
            SET update_status = 'COMPLETE', 
                update_completed = <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                update_response = <cfqueryparam value="#newUpdateResponse#" cfsqltype="cf_sql_varchar">
            WHERE fk_tool_case = <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">
        </cfquery>

        <!--- Update tool_cases with last update timestamp & flag the update --->
        <cfquery datasource="Reach">
            UPDATE docketwatch.dbo.tool_cases 
            SET last_update_completed = <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                new_update_flag = 1
            WHERE tool_case_id = <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">
        </cfquery>

        <!--- Check if an alert already exists for this update --->
        <cfquery name="existingAlert" datasource="Reach">
            SELECT COUNT(*) AS alert_count
            FROM docketwatch.dbo.tool_alerts
            WHERE fk_tool_case = <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">
              AND last_fetch_date_with_updates = <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">;
        </cfquery>

        <!--- Insert alert only if there is no existing alert for this update --->
        <cfif existingAlert.alert_count EQ 0>
            <cfquery datasource="Reach">
                INSERT INTO docketwatch.dbo.tool_alerts 
                    (fk_tool_case, schedule_type, last_track_date, last_fetch_date, last_fetch_date_with_updates, case_api, created_at)
                VALUES
                    (<cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">,
                     <cfqueryparam value="case_update" cfsqltype="cf_sql_varchar">,
                     <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                     <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                     <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                     <cfqueryparam value=NULL cfsqltype="cf_sql_varchar" null="true">,
                     <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">);
            </cfquery>

            <cfoutput>
                <p>New update detected for case #tool_case_id# and alert created.</p>
            </cfoutput>
        <cfelse>
            <cfoutput>
                <p>Update detected for case #tool_case_id#, but an alert already exists.</p>
            </cfoutput>
        </cfif>
    <cfelse>
        <cfoutput>
            <p>Update checked for case #tool_case_id#, but no changes detected.</p>
        </cfoutput>
    </cfif>
</cfif>



    
</cfloop>
