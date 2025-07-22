<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch - Case Events</title>

    <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">

<!--- Page Container --->
<div class="container mt-4">
    <h2 class="mb-4">Scheduled Task Log</h2>
    
    <!--- Scheduled Tasks Table --->
    <table id="scheduledTasksTable" class="table table-striped">
        <thead>
            <tr>
                <th>Task Name</th>
                <th>Description</th>
                <th>Type</th>
                <th>Status</th>
                <th>Last Run</th>
                <th>Next Run</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            <!--- Task Data Will be Loaded Here --->
        </tbody>
    </table>
</div>
 <cfinclude template="footer_script.cfm">
<script>
$(document).ready(function() {
    var table = $('#scheduledTasksTable').DataTable({
        "ajax": "get_scheduled_tasks.cfm?bypass=1",
        "columns": [
            { "data": "task_name" },
            { "data": "description" },
            { "data": "type" },
            { "data": "status" },
            { "data": "last_run" },
            { "data": "next_run" },
            {
                "data": null,
                "defaultContent": "<button class='expand-task btn btn-sm btn-primary'>View Runs</button>"
            }
        ]
    });

    // Handle Task Expansion
    $('#scheduledTasksTable tbody').on('click', 'button.expand-task', function () {
        var tr = $(this).closest('tr');
        var row = table.row(tr);

        if (row.child.isShown()) {
            row.child.hide();
            tr.removeClass('shown');
        } else {
            var taskId = row.data().id;
            $.ajax({
                url: "get_task_runs.cfm?bypass=1&task_id=" + taskId,
                success: function(response) {
var runsTable = `<table class="table">
    <thead><tr>
        <th>Run ID</th>
        <th>Start Time</th>
        <th>End Time</th>
        <th>Status</th>
        <th>Summary</th>
        <th>Cases</th>  <!--- NEW COLUMN --->
        <th>Actions</th>
    </tr></thead><tbody>`;

response.data.forEach(run => {
    runsTable += `<tr>
        <td>${run.id}</td>
        <td>${run.timestamp_started}</td>
        <td>${run.timestamp_ended}</td>
        <td>${run.status}</td>
        <td>${run.summary}</td>
        <td>${run.total_cases}</td>  <!--- NEW COLUMN --->
        <td><button class='expand-run btn btn-sm btn-secondary' data-run="${run.id}">View Logs</button></td>
    </tr>`;
});

                    runsTable += `</tbody></table>`;
                    row.child(runsTable).show();
                    tr.addClass('shown');
                }
            });
        }
    });

    // Handle Run Expansion for Log Entries (Proper Toggle)
    $(document).on('click', '.expand-run', function () {
        var runId = $(this).data('run');
        var btn = $(this);
        var parentRow = $(btn).closest('tr');
        var nextRow = parentRow.next('.log-table-row');

        // If logs are already visible, collapse them
        if (nextRow.length) {
            nextRow.remove();
        } else {
            // Remove any previously open logs before opening a new one
            $('.log-table-row').remove();

            $.ajax({
                url: "get_task_logs.cfm?bypass=1&task_run_id=" + runId,
                success: function(response) {
                    var logsTable = `<table class="table">
                        <thead><tr>
                            <th>Timestamp</th>
                            <th>Type</th>
                            <th>Description</th>
                            <th>Link</th>
                        </tr></thead><tbody>`;

                 response.data.forEach(log => {
    logsTable += `<tr>
        <td>${log.log_timestamp}</td>
        <td>${log.log_type}</td>
        <td>${log.description}</td>
        <td>
            ${log.case_url ? 
                `<a href="${log.case_url}" target="caseView"><i class="fas fa-search"></i></a>` : 
                ``}
        </td>
    </tr>`;
});


                    logsTable += `</tbody></table>`;

                    // Append log table below the clicked row and mark it with a class
                    parentRow.after(`<tr class="log-table-row"><td colspan="6">${logsTable}</td></tr>`);
                }
            });
        }
    });
});

</script>




