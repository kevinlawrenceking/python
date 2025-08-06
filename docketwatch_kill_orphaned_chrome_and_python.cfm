<cfscript>
// Define the full path to the batch file
batFile = "\\10.146.176.84\general\docketwatch\python\docketwatch_kill_orphaned_chrome_and_python.bat";
logFile = "\\10.146.176.84\general\docketwatch\python\logs\kill_orphaned_processes_output.txt";

// Optional: make sure the logs directory exists
logsDir = "\\10.146.176.84\general\docketwatch\python\logs";
if (!directoryExists(logsDir)) {
    directoryCreate(logsDir);
}

// Check if batch file exists
if (!fileExists(batFile)) {
    writeOutput("<strong>ERROR:</strong> Batch file not found: " & batFile & "<br>");
    abort;
}
</cfscript>

<cfoutput><h3>Killing Orphaned Chrome and Python Processes</h3></cfoutput>

<cftry>
    <cfexecute 
        name="cmd.exe"
        arguments="/c ""#batFile#"""
        timeout="300"
        outputfile="#logFile#"
        errorfile="#logFile#"
        variable="result"
    >
    </cfexecute>

    <cfif fileExists(logFile)>
        <cfset logText = fileRead(logFile)>
        <cfif len(trim(logText))>
            <cfoutput><h4>Process Cleanup Results:</h4></cfoutput>
            <cfset resultLines = listToArray(logText, chr(13) & chr(10))>
            <cfloop array="#resultLines#" index="line">
                <cfif len(trim(line))>
                    <cfoutput>#htmlEditFormat(line)#<br></cfoutput>
                </cfif>
            </cfloop>
        <cfelse>
            <cfoutput><strong>INFO:</strong> Process cleanup completed (no output generated).<br></cfoutput>
        </cfif>
    <cfelse>
        <cfoutput><strong>WARNING:</strong> Log file was not created or is not accessible.<br></cfoutput>
    </cfif>

    <cfoutput><hr><strong>Process cleanup completed at:</strong> #dateFormat(now(), "mm/dd/yyyy")# #timeFormat(now(), "HH:mm:ss")#</cfoutput>

    <cfcatch type="any">
        <cfoutput><strong>ERROR:</strong> #cfcatch.message#<br>#cfcatch.detail#</cfoutput>
    </cfcatch>
</cftry>
