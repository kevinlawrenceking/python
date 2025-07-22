<cfsetting enablecfoutputonly="true">
<cfcontent type="application/json">

<cfquery name="getTasks" datasource="Reach">
    WITH LatestRuns AS (
        SELECT 
            fk_scheduled_task, 
            MAX(timestamp_started) AS latest_timestamp
        FROM docketwatch.dbo.task_runs
        GROUP BY fk_scheduled_task
    )
    SELECT 
        t.id, 
        t.task_name, 
        t.description, 
        t.type, 
        COALESCE(r.status, 'Active') AS status, 
        t.filename, 
        t.log_file, 
        t.interval_minutes, 
        r.timestamp_started AS last_run,
        DATEADD(MINUTE, t.interval_minutes, r.timestamp_started) AS next_run
    FROM docketwatch.dbo.scheduled_task t
    LEFT JOIN LatestRuns lr ON t.id = lr.fk_scheduled_task
    LEFT JOIN docketwatch.dbo.task_runs r 
        ON r.fk_scheduled_task = t.id AND r.timestamp_started = lr.latest_timestamp
  WHERE t.type = 'user' and t.status = 'Active'
    ORDER BY t.task_name;
</cfquery>

<!--- Convert Query to JSON Array ---> 
<cfset data = []>

<cfloop query="getTasks">
    <cfset row = {
        "id": getTasks.id,
        "task_name": getTasks.task_name,
        "description": HTMLEditFormat(getTasks.description),
        "type": getTasks.type,
        "status": getTasks.status,
        "filename": getTasks.filename,
        "log_file": getTasks.log_file,
        "interval_minutes": getTasks.interval_minutes,
        "last_run": dateFormat(getTasks.last_run, "MM-dd-yy") & "<br/>" & timeFormat(getTasks.last_run, "h:mm tt"),
        "next_run": dateFormat(getTasks.next_run, "MM-dd-yy") & "<br/>" & timeFormat(getTasks.next_run, "h:mm tt")
    }>
    <cfset arrayAppend(data, row)>
</cfloop>

<!--- Output JSON Response with "data" wrapper --->
<cfoutput>#serializeJSON({ "data": data })#</cfoutput>
