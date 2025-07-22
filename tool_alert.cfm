<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch - Tool Alerts</title>

    <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm" />

<!--- Page Container --->
<div class="container mt-4">
    <h2 class="mb-4">Active Alerts</h2>

    <!--- Tool Alerts Table --->
    <table id="toolAlertsTable" class="table table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <th>Case Name</th>
                <th>Case Number</th>
                <th>Schedule Type</th>
                <th>Last Track Date</th>
                <th>Last Fetch Date</th>
                <th>Last Fetch w/ Updates</th>
                <th>Alert Created</th>
            </tr>
        </thead>
        <tbody>
            <cfquery name="toolAlerts" datasource="Reach">
                SELECT 
                    ta.id AS alert_id,
                    ta.fk_tool_case,
                    tc.case_name,
                    tc.case_number,
                    ta.schedule_type,
                    ta.last_track_date,
                    ta.last_fetch_date,
                    ta.last_fetch_date_with_updates,
                    ta.created_at
                FROM docketwatch.dbo.tool_alerts ta
                INNER JOIN docketwatch.dbo.cases tc 
                    ON ta.fk_tool_case = tc.tool_case_id
                ORDER BY ta.created_at DESC;
            </cfquery>

            <cfoutput query="toolAlerts">
                <tr>
                    <td>#case_name#</td>
                    <td>#case_number#</td>
                    <td>#schedule_type#</td>
                    <td>#DateFormat(last_track_date, 'mm/dd/yyyy')#</td>
                    <td>#DateFormat(last_fetch_date, 'mm/dd/yyyy')#</td>
                    <td>#DateFormat(last_fetch_date_with_updates, 'mm/dd/yyyy')#</td>
                    <td>#DateFormat(created_at, 'mm/dd/yyyy HH:nn:ss')#</td>
                </tr>
            </cfoutput>
        </tbody>
    </table>
</div>

<cfinclude template="footer_script.cfm">

<!--- DataTables Initialization --->
<script>
    $(document).ready(function() {
        $('#toolAlertsTable').DataTable({
            "paging": true,
            "searching": true,
            "ordering": true,
            "info": true
        });
    });
</script>

</body>
</html>
