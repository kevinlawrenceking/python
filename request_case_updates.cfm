--->
<cfquery name="untrackedCases" datasource="Reach">
    SELECT tc.tool_case_id, t.api_key
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    WHERE c.status = 'Tracked'
</cfquery>

<cfloop query="untrackedCases">
    <cfset tool_case_id = untrackedCases.tool_case_id>
    <cfset api_key = untrackedCases.api_key>

    <!--- Construct API URL --->
    <cfset api_url = "https://enterpriseapi.unicourt.com/caseUpdate">

    <!--- Create JSON Body --->
    <cfset request_body = '{
        "caseId": "' & tool_case_id & '"
    }'>

    <!--- Make API Call --->
    <cfhttp url="#api_url#" method="PUT" result="apiResponse">
        <cfhttpparam type="header" name="Authorization" value="Bearer #api_key#">
        <cfhttpparam type="header" name="Content-Type" value="application/json">
        <cfhttpparam type="body" value="#request_body#">
    </cfhttp>

    <!--- Parse API Response --->
    <cfset jsonResponse = DeserializeJSON(apiResponse.fileContent)>

    <cfif StructKeyExists(jsonResponse, "status") AND jsonResponse.status EQ "IN_PROGRESS">
        <!--- Insert into case_update_log --->
        <cfquery datasource="Reach">
            INSERT INTO docketwatch.dbo.case_update_log 
                (fk_tool_case, update_status, update_requested, update_response)
            VALUES 
                (<cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">,
                 <cfqueryparam value="IN_PROGRESS" cfsqltype="cf_sql_varchar">,
                 <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">,
                 <cfqueryparam value="#apiResponse.fileContent#" cfsqltype="cf_sql_varchar">)
        </cfquery>

        <!--- Mark the case as tracked in tool_cases  
        <cfquery datasource="Reach">
            UPDATE docketwatch.dbo.tool_cases 
            SET is_tracked = 1, last_update_requested = <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">
            WHERE tool_case_id = <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">
        </cfquery>

        <cfoutput>
            <p>Tracking request sent for case #tool_case_id# and marked as tracked.</p>
        </cfoutput>
    <cfelse>
        <cfoutput>
            <p>Failed to request tracking for case #tool_case_id#. API Response: #apiResponse.fileContent#</p>
        </cfoutput>
    </cfif>

 Query untracked cases from tool_cases --->
</cfloop>
