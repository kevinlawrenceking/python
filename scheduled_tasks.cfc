<cfsetting showdebugoutput="false">

<cfscript>
    // Load ColdFusion Admin API
    adminObj = createObject("component", "cfide.adminapi.scheduler");

    // Get all scheduled tasks (use getScheduledTasks() instead of listAll())
    tasks = adminObj.getScheduledTasks();

    // Prepare an array for JSON output
    tasksArray = [];

    for (taskName in tasks) {
        taskDetails = adminObj.getTaskDetails(taskName); // Get full task details

        structAppend(taskDetails, { 
            "taskName": taskDetails.task, 
            "taskFile": taskDetails.path, 
            "interval": taskDetails.interval, 
            "startTime": taskDetails.startTime, 
            "endTime": taskDetails.endTime, 
            "lastRun": taskDetails.lastRun, 
            "status": "Active"
        }, true);

        arrayAppend(tasksArray, taskDetails);
    }

    // Output as JSON
    writeOutput(serializeJSON(tasksArray));
</cfscript>
