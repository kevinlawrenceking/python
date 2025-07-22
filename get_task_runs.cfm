<cfsetting enablecfoutputonly="true">
<cfsetting showdebugoutput="false">  
<cfheader name="Content-Type" value="application/json">

<cfparam name="url.task_id" type="numeric">

<cftry>
<!--- Set Target Date (Default to Today) --->
<cfparam name="url.target_date" default="#dateFormat(now(), 'yyyy-mm-dd')#">
<cfset targetDate = url.target_date>

<cfquery name="getRuns" datasource="Reach">
    SELECT 
        r.id, 
        r.fk_scheduled_task, 
        r.timestamp_started, 
        r.timestamp_ended, 
        r.status, 
        r.summary,
        COUNT(DISTINCT c.id) AS total_cases  
    FROM docketwatch.dbo.task_runs r
    LEFT JOIN docketwatch.dbo.task_runs_log l ON l.fk_task_run = r.id   
    LEFT JOIN docketwatch.dbo.cases c ON c.id = l.fk_case  
    WHERE r.fk_scheduled_task = <cfqueryparam value="#url.task_id#" cfsqltype="CF_SQL_INTEGER">
      AND CAST(r.timestamp_started AS DATE) = <cfqueryparam value="#targetDate#" cfsqltype="CF_SQL_DATE">
    GROUP BY r.id, r.fk_scheduled_task, r.timestamp_started, r.timestamp_ended, r.status, r.summary
    ORDER BY r.timestamp_started DESC;
</cfquery>





    <!--- Ensure runs is always defined --->
    <cfset runs = []>

    <cfif getRuns.recordCount GT 0>
       <cfloop query="getRuns">
    <cfset run = {
        "id": getRuns.id,
        "timestamp_started": dateFormat(getRuns.timestamp_started, "yyyy-MM-dd") & " " & timeFormat(getRuns.timestamp_started, "HH:nn:ss"),
        "timestamp_ended": 
            ( getRuns.timestamp_ended NEQ "" ? 
            dateFormat(getRuns.timestamp_ended, "yyyy-MM-dd") & " " & timeFormat(getRuns.timestamp_ended, "HH:nn:ss") 
            : "Pending"),
        "status": getRuns.status,
        "summary": HTMLEditFormat(getRuns.summary),
        "total_cases": getRuns.total_cases   
    }>
    <cfset arrayAppend(runs, run)>
</cfloop>

    </cfif>

    <!--- Corrected JSON Format for DataTables --->
    <cfoutput>#serializeJSON({"data": runs})#</cfoutput>

<cfcatch>
    <cfoutput>#serializeJSON({"error": cfcatch.message})#</cfoutput>
</cfcatch>
</cftry>
