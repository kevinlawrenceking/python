<cfsetting enablecfoutputonly="true">
<cfheader name="Content-Type" value="application/json">

<!--- Ensure task_run_id is provided ---> 
<cfparam name="url.task_run_id" type="numeric" default="0">

<cftry>
    <!--- Fetch Log Entries ---> 
    <cfquery name="getLogs" datasource="Reach">
        SELECT 
            l.log_timestamp, 
            l.log_type, 
            l.[description],
			'case_details.cfm?id=' + CAST(c.id AS NVARCHAR) AS case_url
        FROM docketwatch.dbo.task_runs_log l
		left join [docketwatch].[dbo].[cases] c ON c.id = l.fk_case
        WHERE l.fk_task_run = <cfqueryparam value="#url.task_run_id#" cfsqltype="CF_SQL_INTEGER">
        ORDER BY l.log_timestamp;
    </cfquery>
case_details.cfm?id=
    <!--- Convert Query to JSON Array ---> 
    <cfset logs = []>

    <cfloop query="getLogs">
        <cfset logEntry = {
            "log_timestamp": dateFormat(getLogs.log_timestamp, "yyyy-MM-dd") & " " & timeFormat(getLogs.log_timestamp, "HH:mm:ss"),
            "log_type": getLogs.log_type,
            "description": HTMLEditFormat(getLogs.description),
            "case_url": getLogs.case_url
        }>
        <cfset arrayAppend(logs, logEntry)>
    </cfloop>

    <!--- Ensure JSON response is properly structured ---> 
    <cfoutput>#serializeJSON({"data": logs})#</cfoutput>

<cfcatch>
    <!--- Handle Errors ---> 
    <cfoutput>#serializeJSON({"error": cfcatch.message})#</cfoutput>
</cfcatch>
</cftry>
