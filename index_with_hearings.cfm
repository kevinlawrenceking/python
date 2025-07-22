<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch</title>

    <cfinclude template="head.cfm">
    
    <!--- CSS Addition for Hearings Details Control --->
    <style>
        /* Column for hearings details control */
        td.details-control {
            background: url('images/details_open.png') no-repeat center center;
            cursor: pointer;
        }
        tr.shown td.details-control {
            background: url('images/details_close.png') no-repeat center center;
        }
    </style>
</head>
<body>

<cfinclude template="navbar.cfm">

<!--- Page Container --->
<div class="container mt-4">
    <h2 class="mb-4">New Cases Review</h2>

    <!--- Filter Panel --->
    <div class="card mb-3">
      <div class="card-body">
        <div class="row">
          <div class="col-auto">
            <label for="statusFilter" class="form-label">Status:</label>
            <select id="statusFilter" class="form-select">
              <option value="review">Review</option>
              <option value="tracked">Tracked</option>
            </select>
          </div>
          <div class="col-auto">
            <label for="countyFilter" class="form-label">County:</label>
            <select id="countyFilter" class="form-select">
              <option value="">All Counties</option>
              <!--- Options will be populated from the SQL query --->
            </select>
          </div>
        </div>
      </div>
    </div>

    <!--- Action Panel --->
    <div class="card mb-3">
      <div class="card-body">
        <button id="removeCases" class="btn btn-danger">Remove Cases</button>
        <button id="trackCases" class="btn btn-primary">Track Cases</button>
        <button id="refreshFilters" class="btn btn-secondary">Refresh</button>
      </div>
    </div>

    <!--- Cases Table --->
    <table id="casesTable" class="table table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <!--- New details-control column for hearings --->
                <th></th>
                <th><input type="checkbox" id="select-all"></th>
                <th>ID</th>
                <th>Case Number</th>
                <th>Case Name</th>
                <th>Courthouse</th>
                <th>Division</th>
                <th>Details</th>
                <th>Last Updated</th>
                <th>Possible Celebs</th>
                <th>County</th>
                <th>Status</th>
                <th>Link</th>
            </tr>
            <tr class="filters">
                <th></th>
                <th></th>
                <th><input type="text" class="column-filter" data-column="2" placeholder="Search ID"></th>
                <th><input type="text" class="column-filter" data-column="3" placeholder="Search Case #"></th>
                <th><input type="text" class="column-filter" data-column="4" placeholder="Search Name"></th>
                <th>
                    <select class="column-filter" data-column="5">
                        <option value="">All Courthouses</option>
                    </select>
                </th>
                <th>
                    <select class="column-filter" data-column="6">
                        <option value="">All Divisions</option>
                    </select>
                </th>
                <th><input type="text" class="column-filter" data-column="7" placeholder="Search Details"></th>
                <th><input type="text" class="column-filter" data-column="8" placeholder="Search Date"></th>
                <th>
                    <select class="column-filter" data-column="10">
                        <option value="">All Celebrities</option>
                    </select>
                </th>
                <th><input type="text" class="column-filter" data-column="10" placeholder="Search County"></th>
                <th><input type="text" class="column-filter" data-column="11" placeholder="Search Status"></th>
                <th><input type="text" class="column-filter" data-column="12" placeholder="Search Link"></th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

<cfinclude template="footer_script.cfm">



<!--- DataTables Initialization with Hearings Child Row --->
<script>
// Function to format hearings data into an HTML table
function formatHearings(data) {
    if (!data || data.length === 0) {
        return '<div>No hearings found.</div>';
    }
    var html = '<table class="table table-bordered table-sm">';
    html += '<thead><tr>' +
            '<th>ID</th>' +
            '<th>Type</th>' +
            '<th>Date/Time</th>' +
            '<th>Category</th>' +
            '<th>Courthouse</th>' +
            '<th>Department</th>' +
            '</tr></thead><tbody>';
    $.each(data, function(index, hearing) {
        html += '<tr>' +
                '<td>' + hearing.ID + '</td>' +
                '<td>' + hearing.type + '</td>' +
                '<td>' + hearing.date_time + '</td>' +
                '<td>' + hearing.category + '</td>' +
                '<td>' + hearing.courthouse + '</td>' +
                '<td>' + hearing.department + '</td>' +
                '</tr>';
    });
    html += '</tbody></table>';
    return html;
}

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
            { // Details control column for hearings with plus sign via CSS
                "className": 'details-control',
                "orderable": false,
                "data": null,
                "defaultContent": ''
            },
            { // Checkbox column
                "data": null,
                "orderable": false,
                "className": "select-checkbox",
                "render": function(data, type, row) {
                    return '<input type="checkbox" class="row-checkbox" value="' + row.id + '">';
                }
            },
            { "data": "id", "visible": false },
            { 
                "data": "case_number",
                "className": "nowrap",
                "render": function(data, type, row) {
                    if (row.case_url) {
                        return data + ' <a href="' + row.case_url + '" target="_blank" title="Open Case"><i class="fa-solid fa-up-right-from-square"></i></a>';
                    }
                    return data;
                }
            },
            { 
                "data": "case_name",
                "defaultContent": "(None)",
                "render": function(data, type, row) {
                    return data ? data : "(None)";
                }
            },
            { 
                "data": "court_name",
                "defaultContent": "(Unknown)"
            },
            { 
                "data": "division",
                "defaultContent": "(None)"
            },
            { 
                "data": "notes", "visible": false,
                "defaultContent": "(No Details)",
                "render": function(data, type, row) {
                    return data ? data : "(No Details)";
                }
            },
            { 
                "data": "last_updated", "visible": false,
                "className": "nowrap",
                "defaultContent": "(No Date)"
            },
  { 
        "data": "possible_celebs",
        "defaultContent": "(None)",  
        "render": function(data, type, row) {
            return data ? data.replace(/, /g, "<br>") : "(None)";  //  Fix: Replace blank with "(None)"
        }
    },
            { 
                "data": "county" , "visible": false,
                "defaultContent": "(None)"
            },
            { 
                "data": "status" , "visible": false,
                "defaultContent": "(None)"
            },
            { 
                "data": "case_url",
                "defaultContent": "(None)",
                "render": function(data, type, row) {
                    if (data) {
                        return '<a href="' + data + '" target="_blank">Link</a>';
                    }
                    return "(None)";
                }
            }
        ],
        "paging": true,
        "searching": true,
        "ordering": true,
        "info": true,
        "order": [[8, "desc"]],
        "pageLength": 10,
        "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        "processing": true,
        "serverSide": false
    });
    
    // Event listener for child row (hearings) expansion
    $('#casesTable tbody').on('click', 'td.details-control', function() {
        var tr = $(this).closest('tr');
        var row = table.row(tr);
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        } else {
            // Open this row
            $.ajax({
                url: 'hearings_ajax.cfm',
                data: { case_id: row.data().id },
                dataType: 'json',
                success: function(data) {
                    var childHtml = formatHearings(data);
                    row.child(childHtml).show();
                    tr.addClass('shown');
                },
                error: function(xhr, status, error) {
                    console.error("Error fetching hearings:", error);
                    row.child('<div>Error loading hearings.</div>').show();
                    tr.addClass('shown');
                }
            });
        }
    });
    
    // Existing filtering and dropdown functionality
    $('#countyFilter').on('change', function () {
        var selectedCounty = $(this).val();
        localStorage.setItem('selectedCounty', selectedCounty);
        table.column(10).search(selectedCounty).draw();
        var celebSelect = $('.column-filter[data-column="10"]');
        celebSelect.val('');
        table.column(8).search('').draw();
        if (selectedCounty) {
            $.ajax({
                url: "celebs_ajax.cfm",
                type: "GET",
                data: { county: selectedCounty },
                dataType: "json",
                success: function(data) {
                    celebSelect.empty().append('<option value="">All Celebrities</option>');
                    $.each(data.DATA, function(index, row) {
                        var celebName = row.name;
                        var caseKeywords = row.case_keywords;
                        var displayName = caseKeywords === 1 ? '<strong>' + celebName + ' *</strong>' : celebName;
                        celebSelect.append('<option value="' + celebName + '">' + displayName + '</option>');
                    });
                    celebSelect.val('');
                },
                error: function(xhr, status, error) {
                    console.error("Error fetching celebrities:", error);
                }
            });
        } else {
            celebSelect.empty().append('<option value="">All Celebrities</option>');
            table.column(8).data().unique().sort().each(function(d) {
                if (d) celebSelect.append('<option value="' + d + '">' + d + '</option>');
            });
        }
    });

    $('#statusFilter').on('change', function() {
        var selectedStatus = $(this).val();
        table.column(11).search(selectedStatus).draw();
        if (selectedStatus === 'review') {
            $('h2.mb-4').text('New Cases Review');
        } else if (selectedStatus === 'tracked') {
            $('h2.mb-4').text('Tracked Cases');
        }
    });

    $('#refreshFilters').on('click', function() {
        $('#countyFilter').val('');
        localStorage.removeItem('selectedCounty');
        $('#statusFilter').val('review');
        $('.column-filter').val('');
        table.columns().search('');
        table.search('');
        table.draw();
    });

    $('#casesTable thead tr.filters th').off('click.DT');

    $('.column-filter').on('keyup change', function () {
        var columnIndex = $(this).data('column');
        table.column(columnIndex).search(this.value).draw();
    });

    table.on('init.dt', function() {
        table.columns([5, 6, 8]).every(function() {
            var column = this;
            var select = $('.column-filter[data-column="' + column.index() + '"]');
            select.empty().append('<option value="">All</option>');
            column.data().unique().sort().each(function(d) {
                if (d) select.append('<option value="' + d + '">' + d + '</option>');
            });
        });
    });

    $.ajax({
        url: "counties_ajax.cfm",
        type: "GET",
        dataType: "json",
        success: function(data) {
            var countySelect = $("#countyFilter");
            countySelect.empty().append('<option value="">All Counties</option>');
            $.each(data, function(index, county) {
                countySelect.append('<option value="' + county.name + '">' + county.name + '</option>');
            });
            var savedCounty = localStorage.getItem('selectedCounty');
            if(savedCounty) {
                countySelect.val(savedCounty);
            }
        },
        error: function(xhr, status, error) {
            console.error("Error fetching counties:", error);
        }
    });

    var savedCounty = localStorage.getItem('selectedCounty');
    if (savedCounty) {
        $('#countyFilter').val(savedCounty);
        table.column(10).search(savedCounty).draw();
    }

    $('#countyFilter').on('change', function () {
        var selectedCounty = $(this).val();
        localStorage.setItem('selectedCounty', selectedCounty);
        table.column(10).search(selectedCounty).draw();
        var celebSelect = $('.column-filter[data-column="10"]');
        if (selectedCounty) {
            $.ajax({
                url: "celebs_ajax.cfm",
                type: "GET",
                data: { county: selectedCounty },
                dataType: "json",
                success: function(data) {
                    celebSelect.empty().append('<option value="">All Celebrities</option>');
                    $.each(data, function(index, row) {
                        var celebName = row.name;
                        var caseKeywords = row.case_keywords;
                        var displayName = caseKeywords === 1 ? '<strong>' + celebName + ' *</strong>' : celebName;
                        celebSelect.append('<option value="' + celebName + '">' + displayName + '</option>');
                    });
                    celebSelect.val('');
                },
                error: function(xhr, status, error) {
                    console.error("Error fetching celebrities:", error);
                }
            });
        } else {
            celebSelect.empty().append('<option value="">All Celebrities</option>');
            table.column(8).data().unique().sort().each(function(d) {
                if (d) celebSelect.append('<option value="' + d + '">' + d + '</option>');
            });
        }
    });

    $('#select-all').on('click', function() {
        var isChecked = this.checked;
        $('.row-checkbox').prop('checked', isChecked);
    });

    $('#casesTable tbody').on('click', 'td.select-checkbox', function(event) {
        if (!$(event.target).is('input')) {
            var checkbox = $(this).find('input.row-checkbox');
            checkbox.prop('checked', !checkbox.prop('checked'));
        }
    });

    $('#removeCases').on('click', function() {
        var selectedCases = [];
        $('.row-checkbox:checked').each(function() {
            selectedCases.push($(this).val());
        });
        if (selectedCases.length === 0) {
            alert("No cases selected.");
            return;
        }
        if (confirm("Remove " + selectedCases.length + " cases?")) {
            $.ajax({
                url: "cases_ajax.cfm",
                type: "POST",
                data: { idlist: selectedCases.join(",") },
                success: function(response) {
                    console.log("Cases Removed:", response);
                    table.ajax.reload(null, false);
                },
                error: function(xhr, status, error) {
                    console.error("AJAX Error:", error);
                    alert("Error removing cases. Please try again.");
                }
            });
        }
    });

    $('#trackCases').on('click', function() {
        var selectedCases = [];
        $('.row-checkbox:checked').each(function() {
            selectedCases.push($(this).val());
        });
        if (selectedCases.length === 0) {
            alert("No cases selected.");
            return;
        }
        if (confirm("Track " + selectedCases.length + " cases?")) {
            $.ajax({
                url: "cases_track_ajax.cfm",
                type: "POST",
                data: { idlist: selectedCases.join(",") },
                success: function(response) {
                    console.log("Cases Tracked:", response);
                    table.ajax.reload(null, false);
                },
                error: function(xhr, status, error) {
                    console.error("AJAX Error:", error);
                    alert("Error tracking cases. Please try again.");
                }
            });
        }
    });

    setInterval(function() {
        console.log("Refreshing Table...");
        table.ajax.reload(null, true);
    }, 60000);
});
</script>
 


<cftry>
    <!--- Get the authenticated user's name --->
    <cfset login_name = getauthuser()>
    <cfif NOT isDefined("login_name") OR len(trim(login_name)) EQ 0>
        <cfset login_name = "user">
    </cfif>
    <cfquery datasource="reach">
        INSERT INTO docketwatch.dbo.UserActivity (UserName, PageName, CGI_IP, CGI_UserAgent)
        VALUES (
            <cfqueryparam value="#login_name#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#CGI.SCRIPT_NAME#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#CGI.IP_ADDRESS#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#CGI.HTTP_USER_AGENT#" cfsqltype="cf_sql_varchar">
        );
    </cfquery>
<cfcatch type="any">
    <!--- Optionally log error --->
</cfcatch>
</cftry>
 
</body>
</html>
