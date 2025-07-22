<cfsetting showdebugoutput="false">
<cfscript>
    // Load WDDX data - dynamically determined by environment
    wddxData = application.fileSharePath & "scheduled_tasks.wddx";
    
    // Read WDDX file
    if (!fileExists(wddxData)) {
        writeOutput("Error: WDDX file not found.");
        abort;
    }

    // Parse WDDX
    wddxContent = fileRead(wddxData);
    parsedData = wddxDecode(wddxContent);

    // Connect to DB
    dsn = "Docketwatch";

    // Loop through tasks and insert only ACTIVE ones
    for (taskKey in parsedData) {
        task = parsedData[taskKey];

        // Extract Task Details
        taskName = task["task"];
        taskURL = task["url"];
        status = task["status"];
        startTime = task["start_time"];
        startDate = task["start_date"];
        interval = task["interval"];
        nextFire = task["nextfire"];
        lastFire = task["lastfire"];

        // Only insert active tasks (status = "Running")
        if (status == "Running") {
            queryExecute(
                "INSERT INTO dbo.scheduled_task 
                (task_name, description, status, filename, log_file, start_date, interval_minutes, last_run, next_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    {value: taskName, cfsqltype: "CF_SQL_NVARCHAR"},
                    {value: "Imported from WDDX", cfsqltype: "CF_SQL_NVARCHAR"},
                    {value: status, cfsqltype: "CF_SQL_NVARCHAR"},
                    {value: taskURL, cfsqltype: "CF_SQL_NVARCHAR"},
                    {value: "N/A", cfsqltype: "CF_SQL_NVARCHAR"},
                    {value: startDate, cfsqltype: "CF_SQL_DATE"},
                    {value: interval, cfsqltype: "CF_SQL_INTEGER"},
                    {value: lastFire, cfsqltype: "CF_SQL_TIMESTAMP"},
                    {value: nextFire, cfsqltype: "CF_SQL_TIMESTAMP"}
                ],
                {datasource: dsn}
            );

            writeOutput("Inserted task: " & taskName & "<br>");
        }
    }
</cfscript>
