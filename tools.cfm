<cfquery name="getCounties" datasource="reach">
  SELECT [id], [name] + ', ' + state_code AS display_name
  FROM [docketwatch].[dbo].[counties]
  ORDER BY name, state_code
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Tools</title>
  <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">

<div class="container mt-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Court Tools</h2>
   <A href="tool_add.cfm"> <button class="btn btn-primary" >+ Add New Tool</button></a>
  </div>

  <table id="toolsTable" class="table table-striped table-bordered w-100">
    <thead class="table-dark">
      <tr>
        <th style="display:none;">ID</th>
        <th>Name</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</div>

<!--- Tool Modal --->
<div class="modal fade" id="toolModal" tabindex="-1" aria-labelledby="toolModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered">
    <div class="modal-content">
      <form id="toolForm">
        <div class="modal-header">
          <h5 class="modal-title" id="toolModalLabel">Add or Edit Tool</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>

        <!--- Hidden Tool ID --->
 

        <!--- Modal Form Fields --->
    

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Save Tool</button>
        </div>
      </form>
    </div>
  </div>
</div>

<cfinclude template="footer_script.cfm">

<script>
$(document).ready(function () {
  const table = $('#toolsTable').DataTable({
    ajax: {
      url: 'tool_ajax.cfm?bypass=1',
      dataSrc: ''
    },
    columns: [
      { data: 'tool_id', visible: false },
      { data: 'tool_name' },
{ data: 'tool_id', className: "text-center", render: function(tool_id, type, row) {
  return `<button class="btn btn-sm btn-outline-primary me-1" onclick="location.href='tool_setup.cfm?id=${tool_id}'">Edit</button>`;
}}
    ],
    order: [[1, 'asc']],
    paging: true,
    searching: true,
    ordering: true,
    info: true,
    pageLength: 50,
    lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]]
  });

  setInterval(() => {
    console.log("Refreshing Tools...");
    table.ajax.reload(null, false);
  }, 60000);
});

function showToolModal(tool = null) {
  const form = $('#toolForm')[0];
  form.reset();
$('#tool_id').val(tool.tool_id || tool.id || '');

  if (tool) {
    $('#toolModalLabel').text('Edit Tool');
    for (const key in tool) {
      const $field = $(`#${key}`);
      if ($field.length) {
        const decoded = $("<textarea/>").html(tool[key]).text();
        $field.val(decoded);
      }
    }

    
    //  Handle checkboxes explicitly
    $('#addNew').prop('checked', tool.addNew == 1);
    $('#isLogin').prop('checked', tool.isLogin == 1);
  } else {
    $('#toolModalLabel').text('Add New Tool');
  }

  const modal = new bootstrap.Modal(document.getElementById('toolModal'));
  modal.show();
}

$('#toolForm').on('submit', function (e) {
  e.preventDefault();

  const formElement = document.getElementById('toolForm');
  const formData = new FormData(formElement);

  const plainObject = {};
  for (let [key, value] of formData.entries()) {
    plainObject[key] = value;
  }

  // Manually handle checkboxes
plainObject.addNew = $('#addNew').is(':checked') ? 1 : 0;
plainObject.isLogin = $('#isLogin').is(':checked') ? 1 : 0;

  // Debug log
  console.log("Sending to save_tool.cfm:", plainObject);
console.log("Submitting:", plainObject);
  fetch('save_tool.cfm?bypass=1', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(plainObject)
  })
  .then(res => {
    if (!res.ok) throw new Error("Server returned " + res.status);
    return res.json();
  })
  .then(data => {
    if (data.success) {
      Swal.fire('Success', 'Tool saved.', 'success').then(() => {
        $('#toolModal').modal('hide');
        $('#toolsTable').DataTable().ajax.reload();
      });
    } else {
      Swal.fire('Error', data.message || 'Save failed.', 'error');
    }
  })
  .catch(err => {
    Swal.fire('Error', err.message || 'Request failed.', 'error');
  });
});

</script>

</body>
</html>
