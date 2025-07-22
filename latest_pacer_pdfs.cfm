<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch - Latest PACER PDFs</title>
    <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">

<div class="container mt-4">
    <h2 class="mb-4">Latest PACER PDF Documents</h2>

    <table id="pdfTable" class="table table-striped table-bordered w-100">
        <thead class="table-dark">
            <tr>
                <th>Discovery Date</th>
                <th>Case Number</th>
                <th>Case Name</th>
                <th>Event Date</th>
                <th>Document Title</th>
                <th>PDF</th>
            </tr>
        </thead>
        <tbody>
            <!--- Will be populated via AJAX --->
        </tbody>
    </table>
</div>

<cfinclude template="footer_script.cfm">

<script>
$(document).ready(function () {
    var table = $('#pdfTable').DataTable({
        ajax: {
            url: 'latest_pacer_pdfs_data.cfm',
            dataSrc: ''
        },
        columns: [
            { data: 'formatted_created_at', className: 'nowrap' },
            {
                data: 'case_number',
                className: 'nowrap',
                render: function(data, type, row) {
                    return `<span>${data}</span> <a href="case_details.cfm?id=${row.case_id}" class="ms-2" title="View Case"><i class="fa-solid fa-up-right-from-square"></i></a>`;
                }
            },
            { data: 'case_name', className: 'nowrap' },
            {
                data: 'event_date',
                className: 'nowrap',
                render: function(data) {
                    if (!data) return "(No Date)";
                    const date = new Date(data);
                    return `${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}/${date.getFullYear()}`;
                }
            },
            { data: 'pdf_title' },
            {
                data: 'local_pdf_filename',
                className: 'text-center',
                render: function(data, type, row) {
                    if (data && data.length > 0) {
                        return `<a href="/mediaroot/pacer_pdfs/${data}" target="_blank" class="btn btn-sm btn-outline-success"><i class="fas fa-file-pdf"></i></a>`;
                    }
                    return '';
                }
            }
        ],
        order: [[0, 'desc']],
        paging: true,
        searching: true,
        ordering: true,
        info: true,
        pageLength: 10,
        lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]]
    });

    setInterval(function () {
        console.log("Refreshing PDF Table...");
        table.ajax.reload(null, false);
    }, 60000);
});
</script>

</body>
</html>
