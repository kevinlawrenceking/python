<cfsetting requesttimeout="300">
<cfcontent type="text/html; charset=UTF-8">
<cfparam name="last_checked" default=""/>
<!--- Query the last alert check timestamp --->
<cfquery name="getLastChecked" datasource="Reach">
    SELECT alert_last_checked FROM docketwatch.dbo.utilities where id = 1
</cfquery>
<cfset lastChecked = getLastChecked.alert_last_checked />
<!--- Query the latest records --->
<cfquery name="records" datasource="Reach">
    SELECT TOP 1000 id, file_no, file_name, dob_dod, address, GETDATE() AS now_time
    FROM docketwatch.dbo.records_tmp
    ORDER BY id DESC
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>


    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Surrogate Court Records Alert</title>

    <Cfinclude template="head.cfm">
    <!--- Auto-refresh every 20 seconds --->
    <script>
        setTimeout(function() {
            location.reload();
        }, 20000);
    </script>

    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #222;
            color: white;
            text-align: center;
        }

        h1 {
            font-size: 2.5em;
            margin-top: 20px;
            color: #ffcc00;
        }

        .alert-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 20px;
        }

        .alert {
            width: 80%;
            background-color: #ff0000;
            color: white;
            padding: 20px;
            margin: 10px 0;
            border-radius: 10px;
            font-size: 1.5em;
            font-weight: bold;
            text-transform: uppercase;
            box-shadow: 0 0 20px rgba(255, 0, 0, 0.7);
        }

        .alert span {
            display: block;
            font-size: 1.2em;
            margin-top: 5px;
            font-weight: normal;
        }

        .timestamp {
            margin-top: 20px;
            font-size: 1.2em;
            color: #aaa;
        }
    </style>
</head>
<body>

    <h1>NEW SURROGATE COURT RECORDS</h1>

    <div class="alert-container">
        <cfif records.recordcount EQ 0>
            <div class="alert" style="background-color: #444;">
                No new records found.
            </div>
        <cfelse>
            <cfloop query="records">
                <div class="alert">
                    FILE: <cfoutput>#records.file_no#</cfoutput>
                    <span>Name: <cfoutput>#records.file_name#</cfoutput></span>
                    <span>Date of Birth/Death: <cfoutput>#dateformat(records.dob_dod, 'mm/dd/yyyy')#</cfoutput></span>
                    <span>Address: <cfoutput>#records.address#</cfoutput></span>
                </div>
            </cfloop>
        </cfif>
    </div>

    <div class="timestamp">
       Last Alert Checked: <Cfif #lastchecked# is not ""> <cfoutput>#dateformat(lastChecked, 'mm/dd/yyyy')# #timeformat(lastChecked, 'hh:mm:ss tt')#</cfoutput> <cfelse></cfif>
    </div>


    <cfinclude template="footer_script.cfm">

</body>
</html>
