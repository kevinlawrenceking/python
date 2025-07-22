<cfset adminPassword = "theboss!">

<cfobject type="component" name="scheduler" component="cfide.adminapi.scheduler">
<cfset scheduler.login(adminPassword)>

<!--- Register task --->
<cfset scheduler.updateScheduledTask(
    name="pacer_critical_weekday",
    operation="update",
    startTime="03:00",
    endTime="20:00",
    interval="20",
    publish="http://#application.serverDomain#/docketwatch_scheduler/docketwatch_pacer_scraper_critical.cfm?bypass=1",
    requestTimeOut=600,
    httpMethod="GET",
    daysOfWeek="Monday,Tuesday,Wednesday,Thursday,Friday"
)>
