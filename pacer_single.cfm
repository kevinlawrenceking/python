 
<cfset startTime = now()>
<cfset status = 'Pending'>
<cfset filename_cfm = GetFileFromPath(GetTemplatePath())>
<cfset current_filename = "pacer_single">
<cfset filename_python = current_filename & ".py">
<cfset filename_bat = current_filename & ".bat">
<cfset taskRunID = 0>
 

<cftransaction>
    <!--- Fetch Task Details from Database --->
    <cfquery name="taskQuery" datasource="reach">
        SELECT id, task_name, filename, log_file, start_date, interval_minutes, fk_tool
        FROM docketwatch.dbo.scheduled_task 
        WHERE filename = <cfqueryparam value="#current_Filename#" cfsqltype="CF_SQL_NVARCHAR">
    </cfquery>

    <!--- Validate Task Exists --->
    <cfif taskQuery.recordCount EQ 0>
        <cfthrow message="Scheduled task not found for #current_filename#">
    </cfif>

    <!--- Extract Task Info --->    
    <cfset taskID = taskQuery.id>  
    <cfset taskName = taskQuery.task_name>
    <cfset filename = taskQuery.filename>
    <cfset logFile = taskQuery.log_file>
    <cfset intervalMinutes = taskQuery.interval_minutes>
    <cfset fk_tool = taskQuery.fk_tool>
 

    <!--- Insert Task Run Record (Pending) and Capture ID --->
    <cfquery name="insertTaskRun" datasource="reach">
        INSERT INTO docketwatch.dbo.task_runs 
        (fk_scheduled_task, fk_tool, timestamp_started, status, summary)
        VALUES (
            <cfqueryparam value="#taskID#" cfsqltype="CF_SQL_INTEGER">, 
            <cfqueryparam value="#fk_tool#" cfsqltype="CF_SQL_INTEGER">, 
            <cfqueryparam value="#startTime#" cfsqltype="CF_SQL_TIMESTAMP">, 
            <cfqueryparam value="#status#" cfsqltype="CF_SQL_NVARCHAR">, 
            <cfqueryparam value="#taskName# Task Started" cfsqltype="CF_SQL_NVARCHAR">
        );
        SELECT SCOPE_IDENTITY() AS newTaskRunID;
    </cfquery>

    <!--- Validate Task Run ID --->
    <cfif insertTaskRun.recordCount GT 0 AND isNumeric(insertTaskRun.newTaskRunID)>
        <cfset taskRunID = insertTaskRun.newTaskRunID>
    <cfelse>
        <cfthrow message="Failed to insert task run record.">
    </cfif>

    <!--- Insert Initial Log Entry --->
    <cfquery datasource="reach">
        INSERT INTO docketwatch.dbo.task_runs_log 
        (fk_task_run, log_timestamp, log_type, description)
        VALUES (
            <cfqueryparam value="#taskRunID#" cfsqltype="CF_SQL_INTEGER">, 
            <cfqueryparam value="#startTime#" cfsqltype="CF_SQL_TIMESTAMP">, 
            'INFO', 
            <cfqueryparam value="#taskName# Task Started" cfsqltype="CF_SQL_NVARCHAR">
        )
    </cfquery>
</cftransaction>

 <cfexecute name="u:\DOCKETWATCH\python\pacer_single.bat"
           arguments="#form.id#"
           timeout="99999"
           variable="output"
           errorVariable="errorOutput">
</cfexecute>


<cfset endTime = now()>
<cfset executionTime = dateDiff("s", startTime, endTime)>

<!--- Log Script Errors If Any --->
<cfif len(trim(errorOutput)) GT 0>
    <cfquery datasource="reach">
        INSERT INTO docketwatch.dbo.task_runs_log 
        (fk_task_run, log_timestamp, log_type, description)
        VALUES (
            <cfqueryparam value="#taskRunID#" cfsqltype="CF_SQL_INTEGER">, 
            <cfqueryparam value="#endTime#" cfsqltype="CF_SQL_TIMESTAMP">, 
            'ERROR', 
            <cfqueryparam value="Python Error: #errorOutput#" cfsqltype="CF_SQL_NVARCHAR">
        )
    </cfquery>
</cfif>

<!--- Final Completion Log --->
<cfquery datasource="reach">
    INSERT INTO docketwatch.dbo.task_runs_log 
    (fk_task_run, log_timestamp, log_type, description)
    VALUES (
        <cfqueryparam value="#taskRunID#" cfsqltype="CF_SQL_INTEGER">, 
        <cfqueryparam value="#now()#" cfsqltype="CF_SQL_TIMESTAMP">, 
        'INFO', 
        <cfqueryparam value="#taskName# Task Completed" cfsqltype="CF_SQL_NVARCHAR">
    )
</cfquery>

<!--- Update Task Run to Success --->
<cfquery datasource="reach">
    UPDATE docketwatch.dbo.task_runs 
    SET timestamp_ended = <cfqueryparam value="#endTime#" cfsqltype="CF_SQL_TIMESTAMP">,
        status = 'Success',
        summary = <cfqueryparam value="#taskName# Task Completed in #executionTime# seconds" cfsqltype="CF_SQL_NVARCHAR">
    WHERE id = <cfqueryparam value="#taskRunID#" cfsqltype="CF_SQL_INTEGER">
</cfquery>
 
 
 
