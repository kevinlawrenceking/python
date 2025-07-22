<cfsetting showdebugoutput="false">
<cfscript>
    // Load WDDX file path - dynamically determined by environment
    wddxFilePath = application.fileSharePath & "scheduled_tasks.wddx";
    
    // Read the WDDX file
    if (!fileExists(wddxFilePath)) {
        writeOutput("Error: WDDX file not found.");
        abort;
    }

    wddxContent = fileRead(wddxFilePath);
    
    // Convert WDDX into XML
    xmlData = xmlParse(wddxContent);

    // Debugging: Dump XML structure
    writeDump(var=xmlData, label="XML Data Structure");

    // Ensure XML structure is valid
    if (!structKeyExists(xmlData, "wddxPacket") || !structKeyExists(xmlData.wddxPacket, "data") || !structKeyExists(xmlData.wddxPacket.data, "array")) {
        writeOutput("Error: Invalid WDDX format.");
        abort;
    }

    taskArray = xmlData.wddxPacket.data.array.xmlChildren;  // Tasks are stored here

    // Connect to DB
    dsn = "reach";  // Correct DSN
    dbPrefix = "docketwatch.dbo.";  // Ensures all queries target `docketwatch` schema

    // Loop through each task in the array
    for (taskStruct in taskArray) {
        if (!isStruct(taskStruct)) {
            continue; // Skip non-struct elements
        }

        // Extract fields dynamically
        taskVars = taskStruct.xmlChildren;
        taskName = structKeyExists(taskVars, "task") ? taskVars.task.xmlText : "Unknown Task";
        taskURL = structKeyExists(taskVars, "url") ? taskVars.url.xmlText : "N/A";
        status = structKeyExists(taskVars, "status") ? taskVars.status.xmlText : "Unknown";
        startDate = structKeyExists(taskVars, "start_date") ? taskVars.start_date.xmlText : "";
        startTime = structKeyExists(taskVars, "start_time") ? taskVars.start_time.xmlText : "";
        interval = structKeyExists(taskVars, "interval") ? taskVars.interval.xmlText : "";
        nextFire = structKeyExists(taskVars, "nextfire") ? taskVars.nextfire.xmlText : "";
        lastFire = structKeyExists(taskVars, "lastfire") ? taskVars.lastfire.xmlText : "";

        // Convert empty values to NULL
        if (len(trim(taskName)) == 0) taskName = "Unknown Task";
        if (len(trim(taskURL)) == 0) taskURL = "N/A";
        if (len(trim(startDate)) == 0) startDate = null;
        if (len(trim(interval)) == 0) interval = null;
        if (len(trim(nextFire)) == 0) nextFire = null;
        if (len(trim(lastFire)) == 0) lastFire = null;

        // Only insert active tasks (status = "Running")
        if (status == "Running") {
            queryExecute(
                "INSERT INTO #dbPrefix#scheduled_task 
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
