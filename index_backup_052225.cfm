<cfset currentuser = getAuthUser()>
<!--- Check for URL parameter --->
<cfparam name="url.status" default="Review">

<cfparam name="idlist" default="">

<cfquery name="owners" datasource="Reach">
    SELECT 
        username AS value,
        firstname + ' ' + lastname AS display
    FROM docketwatch.dbo.users
    WHERE userRole = 'User'
    ORDER BY 
        CASE WHEN username = <cfqueryparam value="#currentUser#" cfsqltype="cf_sql_varchar"> THEN 0 ELSE 1 END,
        firstname, lastname
</cfquery>
<cfquery name="celebrities" datasource="Reach">
    SELECT DISTINCT ce.id, ce.name as celebrity_name
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts co ON co.court_code = c.fk_court
    INNER JOIN docketwatch.dbo.counties ct ON ct.id = co.fk_county
    INNER JOIN docketwatch.dbo.case_celebrity_matches cm ON cm.fk_case = c.id
	INNER JOIN docketwatch.dbo.celebrities ce on ce.id = cm.fk_celebrity
    WHERE cm.match_status <> 'Removed'
    AND cm.match_status <> 'Removed'
	ORDER BY ce.name
</cfquery>

<cfquery name="tools" datasource="Reach">
    SELECT id, tool_name
    FROM docketwatch.dbo.tools
    where id in (
    select distinct fk_tool from [docketwatch].[dbo].[cases] where fk_tool is not null)
    ORDER BY tool_name
</cfquery>
<cfquery name="states" datasource="Reach">
    SELECT state_code, state_name
    FROM docketwatch.dbo.states
    ORDER BY state_name
</cfquery>
<cfquery name="courts" datasource="Reach">
SELECT c.[court_code]
      ,c.[court_name]
      ,c.[fk_county]
	  ,o.[state_code]
  FROM [docketwatch].[dbo].[courts] c
  INNER JOIN [docketwatch].[dbo].[counties] o ON o.id = c.fk_county
  ORDER by c.[court_name]
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DocketWatch</title>

    <Cfinclude template="head.cfm">

</head>
<body>

<Cfinclude template="navbar.cfm">

<!--- Page Container --->
<!--- Page Container --->
<div class="container mt-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="mb-0 page-title">New Cases Review</h2>
<select id="statusFilter" class="form-select form-select-sm w-auto">
    <option value="Review" <cfif url.status EQ "Review">selected</cfif>>For Review</option>
    <option value="Tracked" <cfif url.status EQ "Tracked">selected</cfif>>Tracked</option>
    <option value="Removed" <cfif url.status EQ "Removed">selected</cfif>>Removed</option>
</select>
    </div>



<!--- Filter Panel --->
<!--- Filter Panel --->
<div class="card mb-3">
  <div class="card-body">
    <div class="row g-3 align-items-end">

      <!--- Owner --->
      <div class="col-auto">
<select id="ownerFilter" class="form-select form-select-sm">
    <option value="">All</option>
    <cfoutput query="owners">
        <option value="#value#" <cfif value EQ currentUser>selected</cfif>>#display#</option>
    </cfoutput>
</select>

      </div>

 
<!--- Tool --->
<div class="col-auto">
  <select id="toolFilter" name="toolFilter" class="form-select form-select-sm case-filter">
    <option value="">All Tools</option>
  </select>
</div>

<!--- State --->
<div class="col-auto">
  <select id="stateFilter" name="stateFilter" class="form-select form-select-sm case-filter">
    <option value="">All States</option>
  </select>
</div>

<!--- County --->
<div class="col-auto">
  <select id="county_id" name="county_id" class="form-select form-select-sm case-filter">
    <option value="">All Counties</option>
  </select>
</div>

<!--- Courthouse --->
<div class="col-auto">
  <select id="courthouseFilter" name="courthouseFilter" class="form-select form-select-sm case-filter">
    <option value="">All Courthouses</option>
  </select>
</div>

<!--- Celebrity --->
<div class="col-auto">
  <select id="celebrityFilter" name="celebrityFilter" class="form-select form-select-sm case-filter">
    <option value="">All Celebrities</option>
  </select>
</div>




    </div>
  </div>
</div>

<!--- Document (OCR) Search Row --->
<div class="card mb-3">
  <div class="card-body">
    <div class="row">
      <div class="col">
        <input type="text" class="form-control" id="documentSearch" placeholder="Search document OCR text..." autocomplete="off">
      </div>
    </div>
  </div>
</div>
<!--- Action Panel --->
<div class="card mb-3">
<div class="card-body">
<Cfoutput>
<button id="removeCases"   class="btn btn-danger">Remove Cases</button>
<button id="trackCases"   class="btn btn-primary">Track Cases</button>
<button id="ReviewCases"  class="btn btn-primary">Set to Review</button>
<a href="add_blank_case.cfm"><button id="AddCase" class="btn btn-primary" >Track a New Case</button></a>
<button id="refreshFilters" class="btn btn-secondary">Refresh</button>

</cfoutput>

  </div>
</div>


    <!--- Cases Table --->
    <table id="casesTable" class="table w-100 table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <th><input type="checkbox" id="select-all"></th>
                <th>Source</th>
                <th style="display:none;">ID</th> <!--- ADD THIS for 'id' --->
                <th>Case Number</th>
                <th>Case Name</th>
                <th>Courthouse</th>
                <th>Priority</th>
                <th>Details</th>
                <th>Last Updated</th>
                <th nowrap>Possible Celebs</th>
                <th>County</th>
                <th>Status</th>
                <th>Link</th>
            </tr>
            <!--- filters no longer needed
            <tr class="filters">
                <th></th>
                <th><input type="text" class="column-filter" data-column="1" placeholder="Search ID"></th>
                <th><input type="text" class="column-filter" data-column="2" placeholder="Search Case #"></th>
                <th><input type="text" class="column-filter" data-column="3" placeholder="Search Name"></th>
                <th>
                    <select class="column-filter" data-column="4">
                        <option value="">All Courthouses</option>
                    </select>
                </th>
                <th>
                    <select class="column-filter" data-column="5">
                        <option value="">All Divisions</option>
                    </select>
                </th>
                <th><input type="text" class="column-filter" data-column="6" placeholder="Search Details"></th>
                <th><input type="text" class="column-filter" data-column="7" placeholder="Search Date"></th>
                <th>
                    <select class="column-filter" data-column="8">
                        <option value="">All Celebrities</option>
                    </select>
                </th>
            </tr>
            --->

        </thead>
        <tbody></tbody>
    </table>
</div>


<cfinclude template="footer_script.cfm">

<script>
$(document).ready(function () {
    window.table = $('#casesTable').DataTable({
        ajax: {
            url: "cases_ajax.cfm",
            data: function (d) {
                d.status     = $('#statusFilter').val();
                d.county     = $('#county_id').val();       // Correct County ID
                d.tool       = $('#toolFilter').val();
                d.owner      = $('#ownerFilter').val();
                d.state      = $('#stateFilter').val();
                d.courthouse = $('#courthouseFilter').val();
                d.celebrity  = $('#celebrityFilter').val();  // Correct Celebrity ID
                d.docsearch  = $('#documentSearch').val(); // <--- Add this!
            },
            dataSrc: function (json) {
                console.log("AJAX Response Data:", json);
                return Array.isArray(json) ? json : [];
            },
            error: function (xhr, error, thrown) {
                console.error("AJAX Error:", error, thrown);
            }
        },
        columns: [
            {
                data: null,
                orderable: false,
                className: "select-checkbox",
                render: function (data, type, row) {
                    return '<input type="checkbox" class="row-checkbox" value="' + row.id + '">';
                }
            },
             { data: "tool_name", title: "Source", defaultContent: "(None)" }, 
            { data: "id", visible: false },
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

          // Add PDF icon if available
        if (row.pdf_link) {
            html += '<a href="' + row.pdf_link + '" target="_blank" title="View PDF" class="text-danger ms-2">'
                  + '<i class="fa-solid fa-file-pdf"></i></a>';
        }

        return data + ' ' + html;
    }
},

            {
                data: "case_name",
                defaultContent: "(None)",
                render: function (data) {
                    return data || "(None)";
                }
            },
            { data: "court_name", defaultContent: "(Unknown)" },
            { data: "priority", defaultContent: "(None)" },
            {
                data: "notes",
                visible: false,
                defaultContent: "(No Details)",
                render: function (data) {
                    return data || "(No Details)";
                }
            },
{
  data: "sortable_last_updated",
  className: "nowrap",
  render: function (data, type, row) {
    if (type === 'display') {
      return row.formatted_last_updated || "(No Date)";
    }
    return data; // raw value for sorting and filtering
  }
}
,
            {
                data: "possible_celebs",
                defaultContent: "(None)",
                render: function (data) {
                    return data ? data.replace(/, /g, "<br>") : "(None)";
                }
            },
            { data: "county", visible: false, defaultContent: "(None)" },
            { data: "status", visible: false, defaultContent: "(None)" },
            { data: "case_url", visible: false, defaultContent: "(None)" }
        ],
        paging: true,
        searching: true,
        ordering: true,
        info: true,
        order: [[8, "desc"]],
        pageLength: 10,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        processing: true,
        serverSide: false
    });

    var initialStatus = $('#statusFilter').val();
    var statusText = {
        "Review": "New Cases Review",
        "Tracked": "Tracked Cases",
        "Removed": "Removed Cases"
    }[initialStatus] || "Cases";
    $('.page-title').text(statusText);

 
// Unified Filter Change Handlers
$('#toolFilter, #county_id, #courthouseFilter, #celebrityFilter, #ownerFilter, #stateFilter, #statusFilter').on('change', function () {
    const id = $(this).attr('id');
    const val = $(this).val();

    if (id === 'toolFilter') {
        localStorage.setItem('selectedTool', val);
    }
    if (id === 'ownerFilter') {
        localStorage.setItem('docketwatch_owner', val);
    }
    if (id === 'courthouseFilter') {
        localStorage.setItem('selectedCourthouse', val);
    }
    if (id === 'county_id') {
        localStorage.setItem('selectedCounty', val);
    }
    if (id === 'stateFilter') {
        localStorage.setItem('selectedState', val);
    }
    if (id === 'celebrityFilter') {
        localStorage.setItem('selectedCelebrity', val);
    }

    reloadDropdowns(); 
    $('#casesTable').DataTable().ajax.reload();

    if (id === 'statusFilter') {
        const statusText = {
            "Review": "New Cases Review",
            "Tracked": "Tracked Cases",
            "Removed": "Removed Cases"
        }[val] || "Cases";
        $('.page-title').text(statusText);
    }
});

$('#documentSearch').on('input', function() {
    $('#casesTable').DataTable().ajax.reload();
});

// Initially hide all buttons
    $('#removeCases, #trackCases, #trackCaseModalBtn, #refreshFilters').hide();

    function updateActionButtons() {
        const status = $('#statusFilter').val();
        const anyChecked = $('.row-checkbox:checked').length > 0;

        // Show Remove button: status = Review AND checkbox selected
        if (status === 'Review' && anyChecked) {
            $('#removeCases').show();
      
        } else {
            $('#removeCases').hide();
        
        }

     // Show Remove button: status = Review AND checkbox selected
        if (status === 'Tracked') {
            $('#trackAdd').show();
      
        } else {
            $('#trackAdd').hide();
        
        }

     // Show Remove button: status = Review AND checkbox selected
        if (status === 'Tracked' && anyChecked) {
            $('#ReviewCases').show();
      
        } else {
            $('#ReviewCases').hide();
        
        }


        

        // Show Track buttons only on Review (not Tracked)
        if (status === 'Review' && anyChecked) {
            $('#trackCases, #trackCaseModalBtn').show();
        } else {
            $('#trackCases, #trackCaseModalBtn').hide();
        }

        // Show Refresh if any filter is active
        const filters = [
            '#toolFilter',
            '#ownerFilter',
            '#stateFilter',
            '#county_id',
            '#courthouseFilter',
            '#celebrityFilter'
        ];

        const anyFilterSet = filters.some(sel => $(sel).val()?.length > 0);
        if (anyFilterSet) {
            $('#refreshFilters').show();
        } else {
            $('#refreshFilters').hide();
        }
    }

    // Event listeners
    $(document).on('change', '.row-checkbox', updateActionButtons);
    $('#statusFilter, #toolFilter, #ownerFilter, #stateFilter, #county_id, #courthouseFilter, #celebrityFilter')
        .on('change', updateActionButtons);

    $('#casesTable').on('draw.dt', updateActionButtons);

    // Refresh resets everything
    $('#refreshFilters').on('click', function () {
        localStorage.clear();
        location.reload();
    });
});
</script>

 
    


<script>
$(document).ready(function () {

    reloadDropdowns();
    var storedState = localStorage.getItem('selectedState');
    if (storedState && $('#stateFilter option[value="' + storedState + '"]').length > 0) {
        $('#stateFilter').val(storedState);
    }

    // Same for county and courthouse
    var storedCounty = localStorage.getItem('selectedCounty');
    if (storedCounty && $('#county_id option[value="' + storedCounty + '"]').length > 0) {
        $('#county_id').val(storedCounty);
    }

    var storedCourthouse = localStorage.getItem('selectedCourthouse');
    if (storedCourthouse && $('#courthouseFilter option[value="' + storedCourthouse + '"]').length > 0) {
        $('#courthouseFilter').val(storedCourthouse);
    }

    var storedCelebrity = localStorage.getItem('selectedCelebrity');
    if (storedCelebrity && $('#celebrityFilter option[value="' + storedCelebrity + '"]').length > 0) {
        $('#celebrityFilter').val(storedCelebrity);
    }
});

</script>


<!--- Reload County Dropdown via AJAX --->
<script>
function reloadDropdowns() {
  var filters = {
    status: $('#statusFilter').val(),
    tool: $('#toolFilter').val(),
    owner: $('#ownerFilter').val(),
    state: $('#stateFilter').val(),
    county: $('#county_id').val(),
    courthouse: $('#courthouseFilter').val(),
    fk_celebrity: $('#celebrityFilter').val()
  };

  const loaders = [
    { url: 'get_tools.cfm', target: '#toolFilter', selected: localStorage.getItem('selectedTool') },
    { url: 'get_states.cfm', target: '#stateFilter', selected: localStorage.getItem('selectedState') },
    { url: 'get_counties.cfm', target: '#county_id', selected: localStorage.getItem('selectedCounty') },
    { url: 'get_courthouses.cfm', target: '#courthouseFilter', selected: localStorage.getItem('selectedCourthouse') },
    { url: 'get_celebrities.cfm', target: '#celebrityFilter', selected: localStorage.getItem('selectedCelebrity') }
  ];

  loaders.forEach(item => {
    $.get(item.url, filters, function(data) {
      $(item.target).html(data);
      if (item.selected) {
        $(item.target).val(item.selected);
      }
    });
  });
}
</script>
<Script>
$('#refreshFilters').on('click', function () {
    // Clear localStorage
    localStorage.removeItem('docketwatch_owner');
    localStorage.removeItem('selectedTool');
    localStorage.removeItem('selectedState');
    localStorage.removeItem('selectedCounty');
    localStorage.removeItem('selectedCourthouse');
    localStorage.removeItem('selectedCelebrity');

    // Reset filters to default values
    $('#statusFilter').val('Review');
    $('#toolFilter').val('');
    $('#ownerFilter').val('');
    $('#stateFilter').val('');
    $('#county_id').val('');
    $('#courthouseFilter').val('');
    $('#celebrityFilter').val('');

    // Reload dropdowns and table
    reloadDropdowns();
    $('#casesTable').DataTable().ajax.reload();

    // Reset page title
    $('.page-title').text('New Cases Review');
});
</script>

<script>
$(document).ready(function () {
    
    $('#select-all').on('click', function() {
        var isChecked = this.checked;
        $('.row-checkbox').prop('checked', isChecked).trigger('change');
    });
  
    $('#casesTable tbody').on('click', 'td.select-checkbox', function(event) {
        if (!$(event.target).is('input')) {
            var checkbox = $(this).find('input.row-checkbox');
            checkbox.prop('checked', !checkbox.prop('checked')).trigger('change');
        }
    });

});
</script>


<script>
function updateCaseStatus(caseId, newStatus) {
    Swal.fire({
        title: 'Are you sure?',
        text: 'Set selected cases to ' + newStatus + '?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#aaa',
        confirmButtonText: 'Yes, set it!'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('update_case_status_list.cfm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ idlist: caseId, status: newStatus })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        title: 'Updated!',
                        text: 'Status updated successfully.',
                        icon: 'success'
                    }).then(() => {
                        saveFiltersToLocalStorage();

                        // This now works because "table" is global
                        table.ajax.reload(null, false);
                        $('.row-checkbox').prop('checked', false);
                        updateActionButtons();
                    });
                } else {
                    Swal.fire('Error', 'Error updating status: ' + data.message, 'error');
                }
            })
            .catch(error => Swal.fire('Error', 'An error occurred: ' + error, 'error'));
        }
    });
}

</script>

<script>
$('#removeCases').on('click', function () {
    const selected = getSelectedCaseIds();
    if (selected.length === 0) return alert("No cases selected.");
    updateCaseStatus(selected.join(','), 'Removed');
});

$('#trackCases').on('click', function () {
    const selected = getSelectedCaseIds();
    if (selected.length === 0) return alert("No cases selected.");
    updateCaseStatus(selected.join(','), 'Tracked');
});

$('#ReviewCases').on('click', function () {
    const selected = getSelectedCaseIds();
    if (selected.length === 0) return alert("No cases selected.");
    updateCaseStatus(selected.join(','), 'Review');
});
</script>

<Script>
function getSelectedCaseIds() {
    const ids = [];
    $('.row-checkbox:checked').each(function () {
        ids.push($(this).val());
    });
    return ids;
}
</script>

<script>
function saveFiltersToLocalStorage() {
    localStorage.setItem('statusFilter', $('#statusFilter').val());
    localStorage.setItem('toolFilter', $('#toolFilter').val());
    localStorage.setItem('ownerFilter', $('#ownerFilter').val());
    localStorage.setItem('stateFilter', $('#stateFilter').val());
    localStorage.setItem('countyFilter', $('#county_id').val());
    localStorage.setItem('courthouseFilter', $('#courthouseFilter').val());
    localStorage.setItem('celebrityFilter', $('#celebrityFilter').val());
    } //   closing brace added
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
    <!--- Optionally log the error or simply ignore it --->
    <!--- <cflog file="errorLog" text="Error logging user activity: #cfcatch.message#"> --->
</cfcatch>
</cftry>


 
<div class="modal fade" id="trackCaseModal" tabindex="-1" aria-labelledby="trackCaseModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="trackCaseModalLabel">Track a New Case</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <form id="trackCaseForm">
        <Cfoutput><input type="hidden" id="currentuser" name="currentuser" value="#currentuser#"></cfoutput>
          <div class="mb-3">
            <label for="toolSelect" class="form-label">Tool <span class="text-danger">*</span></label>
            <select class="form-select" id="toolSelect" required onchange="updateFieldRequirements()">
              <option value="">Select Tool</option>
              <cfquery name="getUserTools" datasource="Reach">
                SELECT [id] as fk_tool, [tool_name]
                FROM [docketwatch].[dbo].[tools]
                WHERE owners LIKE <cfqueryparam value="%#currentUser#%" cfsqltype="cf_sql_varchar">
                and addNew = 1
                ORDER BY tool_name
              </cfquery>
              <cfoutput query="getUserTools">
                <option value="#fk_tool#">#tool_name#</option>
              </cfoutput>
            </select>
          </div>

<!--- Case URL --->
<div class="mb-3" id="caseUrlGroup" style="display: none;">
  <label for="caseUrl" class="form-label">Case URL <span class="text-danger">*</span></label>
  <input type="text" class="form-control" id="caseUrl">
</div>

<!--- Case Number --->
<div class="mb-3" id="caseNumberGroup" style="display: none;">
  <label for="caseNumber" class="form-label">Case Number <span class="text-danger">*</span></label>
  <input type="text" class="form-control" id="caseNumber">
</div>

<!--- Case Name --->
<div class="mb-3" id="caseNameGroup" style="display: none;">
  <label for="caseName" class="form-label">Case Name</label>
  <input type="text" class="form-control" id="caseName">
</div>

        </form>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-primary" onclick="submitNewCase()">Submit</button>
      </div>

      
    </div>
  </div>
</div>


<script>
function updateFieldRequirements() {
  const tool = document.getElementById('toolSelect').value;
  const caseUrlGroup = document.getElementById('caseUrlGroup');
  const caseNumberGroup = document.getElementById('caseNumberGroup');
  const caseNameGroup = document.getElementById('caseNameGroup');
  const caseUrl = document.getElementById('caseUrl');
  const caseNumber = document.getElementById('caseNumber');
  const caseName = document.getElementById('caseName');

  // Reset all
  caseUrlGroup.style.display = 'none';
  caseNumberGroup.style.display = 'none';
  caseNameGroup.style.display = 'none';
  caseUrl.required = false;
  caseNumber.required = false;

  if (tool === "2") {
    caseUrlGroup.style.display = 'block';
    caseUrl.required = true;
  } else if (tool === "13") {
    caseNumberGroup.style.display = 'block';
    caseNumber.required = true;
  } else if (tool === "25") {
    caseNumberGroup.style.display = 'block';
    caseNumber.required = true;
  }
}


// Update on tool selection
document.getElementById('toolSelect').addEventListener('change', updateFieldRequirements);

// Run on load to apply if tool is preselected
</script>

<script>
function submitNewCase() {
  const tool = document.getElementById('toolSelect').value;
  const caseUrlEl = document.getElementById('caseUrl');
  const caseNumberEl = document.getElementById('caseNumber');
  const caseNameEl = document.getElementById('caseName');
  const currentuser = document.getElementById('currentuser').value.trim();

  // Only send fields that are visible
  const caseUrl = caseUrlEl.offsetParent !== null ? caseUrlEl.value.trim() : '';
  const caseNumber = caseNumberEl.offsetParent !== null ? caseNumberEl.value.trim() : '';
  const caseName = caseNameEl.offsetParent !== null ? caseNameEl.value.trim() : '';

Swal.fire({
  title: 'Tracking Case...',
  html: 'Please wait while the case is processed.',
  allowOutsideClick: false,
  didOpen: () => {
    Swal.showLoading();
  }
});

  if (!tool) {
    Swal.fire('Validation Error', 'Please select a tool.', 'warning');
    return;
  }

  fetch('insert_new_case.cfm?bypass=1', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, caseUrl, caseNumber, caseName, currentuser })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success && data.inserted_case_id) {
      Swal.fire('Success', 'Case added successfully.', 'success')
        .then(() => window.location.href = `case_details.cfm?id=${data.inserted_case_id}`);
    } else {
      Swal.fire('Error', data.message || 'Unknown error', 'error');
    }
  })
  .catch(err => Swal.fire('Error', err.message || err, 'error'));
}


</script>
 

</body>
</html>
