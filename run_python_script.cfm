<cftry>
    <!--- Define the command to run the Python script --->
    <cfset pythonCommand = "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Python 3.12\python.exe c:\Python\script.py">

    <!--- Run the command --->
    <cfexecute name="#pythonCommand#" variable="output" errorVariable="errorOutput" timeout="300"></cfexecute>

    <!--- Output the result for debugging --->
    <cfoutput>
        <pre>
        <strong>Script Output:</strong>
        #output#
        <br><br>
        <strong>Error Output:</strong>
        #errorOutput#
        </pre>
    </cfoutput>

<cfcatch>
    <cfoutput>
        <p style="color:red;">Error Running Script: #cfcatch.message#</p>
    </cfoutput>
</cfcatch>
</cftry>
