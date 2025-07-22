<!--- Step 1: Build full list of (case_id, username) combinations from tools --->
<cfquery name="getCaseOwners" datasource="reach">
    SELECT c.id AS case_id, t.owners AS tool_owners
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.tools t ON c.fk_tool = t.id
    WHERE c.status = 'Tracked' AND t.owners IS NOT NULL
</cfquery>

<!--- Step 2: Loop and collect insertable rows --->
<cfset insertList = []>

<cfloop query="getCaseOwners">
    <cfset caseId = getCaseOwners.case_id>
    <cfset ownerList = deserializeJson(trim(getCaseOwners.tool_owners))>

    <cfloop array="#ownerList#" index="username">
        <cfset cleanUsername = trim(username)>

        <!--- Check if user exists --->
        <cfquery name="checkUser" datasource="reach">
            SELECT username FROM docketwatch.dbo.users 
            WHERE username = <cfqueryparam value="#cleanUsername#" cfsqltype="cf_sql_varchar">
        </cfquery>

        <cfif checkUser.recordCount>
            <!--- Check if combination already exists --->
            <cfquery name="checkExisting" datasource="reach">
                SELECT 1 FROM docketwatch.dbo.case_email_recipients
                WHERE fk_case = <cfqueryparam value="#caseId#" cfsqltype="cf_sql_integer">
                  AND fk_username = <cfqueryparam value="#cleanUsername#" cfsqltype="cf_sql_varchar">
            </cfquery>

            <cfif NOT checkExisting.recordCount>
                <cfset arrayAppend(insertList, {caseId=caseId, username=cleanUsername})>
            </cfif>
        </cfif>
    </cfloop>
</cfloop>

<!--- Step 3: Bulk insert all collected rows --->
<cfloop array="#insertList#" index="row">
    <cfquery datasource="reach">
        INSERT INTO docketwatch.dbo.case_email_recipients (fk_case, fk_username)
        VALUES (
            <cfqueryparam value="#row.caseId#" cfsqltype="cf_sql_integer">,
            <cfqueryparam value="#row.username#" cfsqltype="cf_sql_varchar">
        )
    </cfquery>
</cfloop>
