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

<div class="container mt-4">
    <h2 class="mb-4">Latest Case Events</h2>

    <table id="caseEventsTable" class="table table-striped table-bordered w-100">
        <thead class="table-dark">
            <tr>      <th>Discovery Date</th>
                <th>Case Number</th>
                <th>Case Name</th>
                <th>Event Date</th>
                <th>Event Description</th>
            </tr>
        </thead>
        <tbody>
            <!--- Will be populated via AJAX --->
        </tbody>
    </table>
</div>

<cfinclude template="footer_script.cfm">

<script>
$(document).ready(function() {
    var table = $('#caseEventsTable').DataTable({
        ajax: {
            url: 'case_events_data.cfm',
            dataSrc: ''
        },
        columns: [
            {
                data: "sortable_created_at",
                className: "nowrap",
                render: function (data, type, row) {
                    if (type === 'display') {
                        return row.formatted_created_at || "(No Date)";
                    }
                    return data;
                }
            },
            {
                data: 'case_number',
                className: "nowrap",
                render: function(data, type, row) {
                    return `<span>${data}</span> <a href="case_details.cfm?id=${row.id}" class="ms-2" title="View Details">
                                <i class="fa-solid fa-up-right-from-square"></i></a>`;
                }
            },
            {
                data: 'case_name',
                className: "nowrap",
            },
            {
                data: 'event_date',
                className: "nowrap",
                render: function(data) {
                    if (!data) return "(No Date)";
                    const date = new Date(data);
                    if (isNaN(date)) return "(Invalid Date)";
                    return `${(date.getMonth()+1).toString().padStart(2,'0')}/${date.getDate().toString().padStart(2,'0')}/${date.getFullYear()}`;
                }
            },
            {
                data: 'event_description',
                render: function (data, type, row) {
                    if (type === 'display' && data && data.length > 150) {
                        var shortText = data.substr(0, 150);
                        shortText = shortText.substr(0, Math.min(shortText.length, shortText.lastIndexOf(" ")));

                        return `
                            <div class="description-wrapper">
                                <span class="short-desc">${shortText}...</span>
                                <span class="full-desc" style="display: none;">${data}</span>
                                <a href="#" class="read-more ms-1">Read More</a>
                            </div>`;
                    }
                    return data;
                }
            }
        ],

        // --- ADDED THIS SECTION ---
        columnDefs: [
            {
                targets: 4, // Target the 5th column (the description)
                className: 'description-column' // Assign the CSS class
            }
        ],
        // -------------------------

        order: [[0, 'desc']],
        paging: true,
        searching: true,
        ordering: true,
        info: true,
        pageLength: 10,
        lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]]
    });

    $('#caseEventsTable tbody').on('click', 'a.read-more', function(e) {
        e.preventDefault();

        var wrapper = $(this).closest('.description-wrapper');
        wrapper.find('.short-desc').hide();
        $(this).hide();
        wrapper.find('.full-desc').show();
    });

    setInterval(function() {
        console.log("Refreshing Case Events...");
        table.ajax.reload(null, false);
    }, 60000);
});
</script>

</body>
</html>
