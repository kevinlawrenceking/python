<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch - Case Matches</title>

    <cfinclude template="head.cfm"> <!--- Bootstrap, FontAwesome, etc. --->
</head>
<body>

<cfinclude template="navbar.cfm">

<!--- Page Container --->
<div class="container mt-4">
    <h2 class="mb-4">Celebrity Case Matches</h2>

    <!--- Case Matches Table --->
    <table id="caseMatchesTable" class="table table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <th nowrap>Case Number</th>
                <th>Case Name</th>
                <th>Celebrity</th>
                  <th>Case Status</th>
                <th>Match Status</th>
                <th nowrap>Date Created</th>
                <th>Ranking Score</th>
                <th>Match Quality</th>
                <th>Actions</th> <!--- NEW COLUMN: Buttons --->
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

<cfinclude template="footer_script.cfm">

<!--- DataTables Initialization --->
<script>
$(document).ready(function () {
    var table = $('#caseMatchesTable').DataTable({
        ajax: {
            url: 'case_matches_ajax.cfm',
            dataSrc: ''
        },
        columns: [
            {
                data: "case_number",
                className: "nowrap",
                render: function (data, type, row) {
                    let html = '<a href="' + row.internal_case_url + '" title="View in DocketWatch" class="text-muted me-2">'
                             + '<i class="fa-solid fa-file-lines"></i></a>';

                    if (row.external_case_url) {
                        html += '<a href="' + row.external_case_url + '" target="_blank" title="Open Official Court Page" class="text-muted">'
                              + '<i class="fa-solid fa-up-right-from-square"></i></a>';
                    }

                    return data + ' ' + html;
                }
            },
            { data: "case_name" },
            {
                data: "celebrity_name",
                className: "nowrap",
                render: function (data, type, row) {
                    return data + ' <a href="celebrity_details.cfm?id=' + row.fk_celebrity + '" title="View Details" class="ms-2"><i class="fa-solid fa-up-right-from-square"></i></a>';
                }
            },
            { data: "case_status" },
            { data: "match_status" },
            {
                data: "formatted_created_at",
                name: "formatted_created_at",
                className: "nowrap",
                render: function (data, type, row) {
                    if (type === 'sort') return row.sortable_created_at; // sort using ISO
                    return data || "(Unknown)";
                }
            },
            {
                data: "ranking_score",
                render: function (data) {
                    return parseFloat(data).toFixed(2);
                }
            },
            {
                data: "ranking_badge",
                render: function (data) {
                    if (data === "hot") {
                        return '<span class="text-danger"><i class="fa-solid fa-fire"></i> Hot Match</span>';
                    } else if (data === "strong") {
                        return '<span class="text-success"><i class="fa-solid fa-check-circle"></i> Strong Match</span>';
                    } else if (data === "possible") {
                        return '<span class="text-warning"><i class="fa-solid fa-triangle-exclamation"></i> Possible Match</span>';
                    } else {
                        return '<span class="text-secondary"><i class="fa-solid fa-ban"></i> Weak Match</span>';
                    }
                }
            },
            {
                data: null,
                className: "text-center nowrap",
                orderable: false,
                render: function (data, type, row) {
                    return `
                        <button class="btn btn-success btn-sm me-2 match-button" data-id="${row.id}" title="Mark as Matched">
                            <i class="fa-solid fa-check"></i>
                        </button>
                        <button class="btn btn-danger btn-sm remove-button" data-id="${row.id}" title="Mark as Removed">
                            <i class="fa-solid fa-xmark"></i>
                        </button>
                    `;
                }
            }
        ],
        order: [[5, "desc"]], /* Sort by ranking_score descending */
        paging: true,
        searching: true,
        ordering: true,
        info: true,
        pageLength: 10,
        lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]]
    });

    // Auto-refresh the table every minute
    setInterval(function () {
        console.log("Refreshing Case Matches...");
        table.ajax.reload(null, false); // false = don't reset pagination
    }, 60000);

    // Button click handlers for Match / Remove
    $('#caseMatchesTable').on('click', '.match-button', function () {
        let matchId = $(this).data('id');
        updateMatchStatus(matchId, 'Matched');
    });

    $('#caseMatchesTable').on('click', '.remove-button', function () {
        let matchId = $(this).data('id');
        updateMatchStatus(matchId, 'Removed');
    });

    function updateMatchStatus(matchId, newStatus) {
        $.ajax({
            url: 'update_match_status.cfm?bypass=1',
            method: 'POST',
            data: {
                id: matchId,
                status: newStatus
            },
            success: function () {
                table.ajax.reload(null, false); // Refresh after update
            },
            error: function () {
                alert('Error updating match status.');
            }
        });
    }
});
</script>

</body>
</html>
