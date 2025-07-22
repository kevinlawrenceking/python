<!--- Step 1: Pull tracked cases that haven’t been log-fixed by name --->
<cfquery name="x" datasource="reach">
    SELECT id, case_name
    FROM docketwatch.dbo.cases
    WHERE logfix_name = 0 AND status = 'Tracked'
</cfquery>

<cfloop query="x">
    <cfset matchedCaseId = x.id>
    <cfset caseName = trim(x.case_name)>

    <!--- Step 2: Find all log entries where description CONTAINS the case_name --->
    <cfquery name="getMatches" datasource="reach">
        SELECT id
        FROM docketwatch.dbo.task_runs_log
        WHERE fk_case IS NULL
        AND CONTAINS(description, <cfqueryparam value='"#caseName#"' cfsqltype="cf_sql_varchar">)
    </cfquery>

    <!--- Step 3: Update each log entry individually --->
    <cfloop query="getMatches">
        <cfif isNumeric(getMatches.id)>
            <cfquery datasource="reach">
                UPDATE docketwatch.dbo.task_runs_log
                SET fk_case = <cfqueryparam value="#matchedCaseId#" cfsqltype="cf_sql_integer">
                WHERE id = <cfqueryparam value="#getMatches.id#" cfsqltype="cf_sql_integer">
            </cfquery>
        </cfif>
    </cfloop>

    <!--- Step 4: Mark case as completed for name-based matching --->
    <cfquery datasource="reach">
        UPDATE docketwatch.dbo.cases
        SET logfix_name = 1
        WHERE id = <cfqueryparam value="#matchedCaseId#" cfsqltype="cf_sql_integer">
    </cfquery>
</cfloop>

<cfoutput>
    Checked #x.recordCount# cases using full-text search on case_name.
</cfoutput>
