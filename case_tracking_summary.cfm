<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Case Tracking Summary</title>
    <Cfinclude template="head.cfm"> <!--- Includes Bootstrap & DataTables CSS --->
</head>
<body>

<Cfinclude template="navbar.cfm"> <!--- Navigation Bar --->

<!--- Page Container --->
<div class="container mt-4">
    <h2 class="mb-4">Case Tracking Summary</h2>

    <!--- Case Tracking Summary Table --->
    <table id="caseTrackingTable" class="table table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <th>Courthouse</th>
                <th>Division</th>
                <th>Last Updated</th>
                <th>Last Tracked Case</th>
                <th>Total Cases</th>
            </tr>
        </thead>
        <tbody></tbody> <!--- Data will be populated dynamically via AJAX --->
    </table>
</div>

<cfinclude template="footer_script.cfm"> <!--- Includes jQuery & DataTables JS --->

<!--- DataTables Initialization with AJAX --->
<script>
    $(document).ready(function() {
        var table = $('#caseTrackingTable').DataTable({
            "ajax": {
                "url": "case_tracking_ajax.cfm",
                "dataSrc": ""
            },
            "columns": [
                { "data": "courthouse" },
                { "data": "division" },
                { "data": "last_updated" },
                { "data": "last_court_number" },
                { "data": "total_cases" }
            ],
            "paging": true,
            "searching": true,
            "ordering": true,
            "info": true,
            "order": [[2, "desc"]],
            "pageLength": 100,
            "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
            "processing": true,
            "serverSide": false
        });

        // Auto-refresh table every 10 seconds
        setInterval(function() {
            console.log("Refreshing Case Tracking Table...");
            table.ajax.reload(null, false);
        }, 10000);
    });
</script>

</body>
</html>
