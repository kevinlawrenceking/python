<cfcontent type="application/json">
<cftry>

<!--- Step 1: Parse JSON input --->
<cfset rawData = fileRead("php://input")>
<cfset requestData = deserializeJson(rawData)>
<cfset currentUser = getAuthUser()>
<cfset status = trim(requestData.status)>
<cfset updates = requestData.updates>

<!--- Validate input --->
<cfif NOT structKeyExists(requestData, "status") OR NOT isArray(updates)>
    <cfoutput>{"success": false, "message": "Missing or invalid input."}</cfoutput>
    <cfexit>
</cfif>

<!--- Step 2: Loop over updates and apply them --->
<cfloop array="#updates#" index="item">
    <cfquery datasource="Reach">
        MERGE docketwatch.dbo.column_visibility_defaults AS target
        USING (SELECT 
            <cfqueryparam value="#currentUser#" cfsqltype="cf_sql_varchar"> AS username,
            <cfqueryparam value="#status#" cfsqltype="cf_sql_varchar"> AS status,
            <cfqueryparam value="#item.column_key#" cfsqltype="cf_sql_varchar"> AS column_key,
            <cfqueryparam value="#item.is_visible#" cfsqltype="cf_sql_bit"> AS is_visible
        ) AS source
        ON target.username = source.username
           AND target.status = source.status
           AND target.column_key = source.column_key
        WHEN MATCHED THEN
            UPDATE SET is_visible = source.is_visible
        WHEN NOT MATCHED THEN
            INSERT (username, status, column_key, is_visible)
            VALUES (source.username, source.status, source.column_key, source.is_visible);
    </cfquery>
</cfloop>

<!--- Step 3: Return success --->
<cfoutput>{"success": true}</cfoutput>

<cfcatch type="any">
    <cfoutput>
    {
        "success": false,
        "message": "#replace(cfcatch.message, '"', "'", "all")#"
    }
    </cfoutput>
</cfcatch>
</cftry>
