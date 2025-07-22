<!--- Step 1: Pull all tracked cases that haven’t been log-fixed --->
<cfquery name="x" datasource="reach">
    SELECT id, case_number
    FROM docketwatch.dbo.cases
    WHERE logfix = 0 AND status = 'Tracked'
</cfquery>

<cfloop query="x">
    <cfset matchedCaseId = x.id>
    <cfset caseNum = x.case_number>
    <cfset matchedLogIds = []>

    <!--- Step 2: Use full-text search to find logs containing the case number --->
    <cfquery name="getMatches" datasource="reach">
        SELECT id
        FROM docketwatch.dbo.task_runs_log
        WHERE fk_case IS NULL
        AND CONTAINS(description, <cfqueryparam value='"#caseNum#"' cfsqltype="cf_sql_varchar">)
    </cfquery>

    <!--- Step 3: Collect valid integer log IDs --->
    <cfloop query="getMatches">
        <cfif isNumeric(getMatches.id)>
            <cfset arrayAppend(matchedLogIds, int(getMatches.id))>
        </cfif>
    </cfloop>

    <!--- Step 4: Update matching log entries --->
    <cfif arrayLen(matchedLogIds)>
        <cfquery datasource="reach">
            UPDATE docketwatch.dbo.task_runs_log
            SET fk_case = <cfqueryparam value="#matchedCaseId#" cfsqltype="cf_sql_integer">
            WHERE id IN (
                <cfqueryparam value="#arrayToList(matchedLogIds)#" cfsqltype="cf_sql_integer" list="true">
            )
        </cfquery>
    </cfif>

    <!--- Step 5: Mark this case as log-fixed --->
    <cfquery datasource="reach">
        UPDATE docketwatch.dbo.cases
        SET logfix = 1
        WHERE id = <cfqueryparam value="#matchedCaseId#" cfsqltype="cf_sql_integer">
    </cfquery>
</cfloop>

<cfoutput>
    Checked #x.recordCount# cases using full-text CONTAINS().
</cfoutput>
