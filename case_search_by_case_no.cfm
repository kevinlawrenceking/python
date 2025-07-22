<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch</title>

    <Cfinclude template="head.cfm">

</head>
<body>

<Cfinclude template="navbar.cfm" />

<!--- Page Container --->
<div class="container mt-4">
    <h2 class="mb-4">Cases List</h2>

    <!--- Cases Table --->
<table id="casesTable" class="table table-striped table-bordered">
    <thead class="table-dark">
        <tr>
            <th>ID</th>
            <th>Case Number</th>
            <th>Case Name</th>
            <th>Courthouse</th>
            <th>Division</th>
            <th>Details</th>
            <th>Last Updated</th>
            <th>Possible Celebs</th>
        </tr>
        <tr class="filters no-sort">
            <th><input type="text" class="column-filter" data-column="0" placeholder="Search ID"></th>
            <th><input type="text" class="column-filter" data-column="1" placeholder="Search Case #"></th>
            <th><input type="text" class="column-filter" data-column="2" placeholder="Search Name"></th>
            <th>
                <select class="column-filter" data-column="3">
                    <option value="">All Courthouses</option>
                </select>
            </th>
            <th>
                <select class="column-filter" data-column="4">
                    <option value="">All Divisions</option>
                </select>
            </th>
            <th><input type="text" class="column-filter" data-column="5" placeholder="Search Details"></th>
            <th><input type="text" class="column-filter" data-column="6" placeholder="Search Date"></th>
            <th>
                <select class="column-filter" data-column="7">
                    <option value="">All Celebrities</option>
                </select>
            </th>
        </tr>
    </thead>
    <tbody></tbody>  
</table>



</div>

<cfinclude template="footer_script.cfm">

<!--- DataTables Initialization with AJAX --->
<script>
$(document).ready(function() {
    var table = $('#casesTable').DataTable({
        "ajax": {
            "url": "cases_ajax.cfm",
            "dataSrc": function(json) {
                console.log("AJAX Response Data:", json);
                return Array.isArray(json) ? json : [];
            },
            "error": function(xhr, error, thrown) {
                console.error("AJAX Error:", error, thrown);
            }
        },
        "columns": [
            { "data": "id", "visible": false },
            { "data": "case_number", "className": "nowrap" },
            { "data": "case_name" },
            { "data": "court_name" },
            { "data": "division" },
            { "data": "notes" },
            { 
                "data": "last_updated",
                "className": "nowrap",
                "render": function(data, type, row) {
                    return data.replace(/\n/g, "<br>");
                }
            },
            { 
                "data": "possible_celebs",
                "defaultContent": "",
                "render": function(data, type, row) {
                    return data ? data.replace(/, /g, "<br>") : "(None)";
                }
            }
        ],
        "paging": true,
        "searching": true,
        "ordering": true,
        "info": true,
        "order": [[0, "desc"]],
        "pageLength": 100,
        "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        "processing": true,
        "serverSide": false,
        "initComplete": function() {
            var api = this.api();

            // Populate Dropdown Filters for Courthouse, Division, & Possible Celebs
            api.columns([3, 4]).every(function() {
                var column = this;
                var select = $('.column-filter[data-column="' + column.index() + '"]');

                column.data().unique().sort().each(function(d, j) {
                    select.append('<option value="' + d + '">' + d + '</option>');
                });
            });

            // 🔹 **Fix the Possible Celebs Filter (One per Line)**
            api.columns(7).every(function() {
                var column = this;
                var select = $('.column-filter[data-column="7"]');

                var celebSet = new Set();
                column.data().each(function(d) {
                    if (d) {
                        d.split(', ').forEach(function(name) {
                            celebSet.add(name.trim());
                        });
                    }
                });

                // Add Celebrities as Unique Filter Options
                Array.from(celebSet).sort().forEach(function(celeb) {
                    select.append('<option value="' + celeb + '">' + celeb + '</option>');
                });
            });
        },
        "columnDefs": [
            { "orderable": false, "targets": $(".filters th").map(function() { return $(this).index(); }).get() }
        ]
    });

    // Apply Column Filtering
    $('.column-filter').on('keyup change', function () {
        var columnIndex = $(this).data('column');
        table.column(columnIndex).search(this.value).draw();
    });

    // Refresh Table Every 10 Seconds
    setInterval(function() {
        console.log("Refreshing Table...");
        table.ajax.reload(null, false);
    }, 10000);
});

</script>


</body>
</html>
