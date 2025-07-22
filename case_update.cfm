<cfparam name="case_mode" default="update">

<cfquery name="getCase" datasource="reach">
SELECT 
    id, 
    case_number, 
    case_name,
    status, 
    fk_court, 
    case_type, 
    case_url, 
    fk_tool, 
    fk_priority
FROM docketwatch.dbo.cases
WHERE id = <cfqueryparam value="#url.id#" cfsqltype="cf_sql_integer">
</cfquery>
<!--- PRIORITY --->
<cfquery name="getPriorities" datasource="reach">
SELECT id, name as display
FROM docketwatch.dbo.case_priority
WHERE id <> 0
ORDER BY id
</cfquery>

<!--- TOOL --->
<cfquery name="getTools" datasource="reach">
SELECT id, tool_name as display
FROM docketwatch.dbo.tools
WHERE id NOT IN (9,10,11,1)
ORDER BY tool_name
</cfquery>

<!--- STATUS --->
<cfquery name="getStatus" datasource="reach">
SELECT DISTINCT status as id, status as display
FROM docketwatch.dbo.cases
ORDER BY status
</cfquery>

<cfquery name="getStates" datasource="reach">
SELECT state_code, state_name FROM docketwatch.dbo.states ORDER BY state_name
</cfquery>

<cfquery name="getCounties" datasource="reach">
SELECT id, name, state_code FROM docketwatch.dbo.counties
ORDER BY name
</cfquery>

<cfquery name="getCourts" datasource="reach">
SELECT o.court_code as id, o.court_name + ' (' + u.name + ')' as display, u.id as county_id, u.state_code
FROM docketwatch.dbo.courts o
INNER JOIN docketwatch.dbo.counties u ON u.id = o.fk_county
ORDER BY o.court_name
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Case Update Form</title>
  <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">
<div class="container mt-5">
  <div class="card shadow">
    <div class="card-header bg-dark text-white">
      <h4 class="mb-0">Update Case Details</h4>
    </div>
    <cfoutput>
    <div class="card-body">
      <form method="post" action="save_case_update.cfm">
        <input type="hidden" name="id" value="#getCase.id#">
<input type="hidden" name="case_mode" value="#case_mode#">



        <div class="mb-3">
          <label for="case_number" class="form-label">Case Number</label>
          <input type="text" class="form-control" id="case_number" name="case_number" value="#getCase.case_number#" >
        </div>
        <div class="mb-3">
          <label for="case_name" class="form-label">Case Name</label>
          <input type="text" class="form-control" id="case_name" name="case_name" value="#getCase.case_name#" >
        </div>

        </cfoutput>
        <div class="mb-3">
          <label for="status" class="form-label">Status</label>
          <select class="form-select" id="status" name="status" >
            <cfoutput query="getStatus">
              <option value="#id#" <cfif getCase.status EQ id>selected</cfif>>#display#</option>
            </cfoutput>
          </select>
        </div>
        <div class="mb-3">
          <label for="fk_priority" class="form-label">Priority</label>
          <select class="form-select" id="fk_priority" name="fk_priority">
            <cfoutput query="getPriorities">
              <option value="#id#" <cfif getCase.fk_priority EQ id>selected</cfif>>#display#</option>
            </cfoutput>
          </select>
        </div>
        <div class="mb-3">
          <label for="fk_tool" class="form-label">Tool</label>
          <select class="form-select" id="fk_tool" name="fk_tool">
            <cfoutput query="getTools">
              <option value="#id#" <cfif getCase.fk_tool EQ id>selected</cfif>>#display#</option>
            </cfoutput>
          </select>
        </div>
       <cfoutput>
  <div class="mb-3">
    <label for="case_url" class="form-label">Case URL</label>
    <input type="text" class="form-control" id="case_url" name="case_url" value="#getCase.case_url#">
  </div>
</cfoutput>

<cfif case_mode NEQ "new">
  <cfoutput>
    <div class="mb-3">
      <label for="case_type" class="form-label">Case Type</label>
      <input type="text" class="form-control" id="case_type" name="case_type" value="#getCase.case_type#">
    </div>
  </cfoutput>

  <!--- Court picker section --->
  <div class="mb-3">
    <label for="stateSelect" class="form-label">State</label>
    <select id="stateSelect" class="form-select">
      <option value="">Select State</option>
      <cfoutput query="getStates">
        <option value="#state_code#"
          <cfif getCase.fk_court neq "" and getCase.fk_court eq getCourts.id and getCourts.state_code eq state_code>
            selected
          </cfif>
        >#state_name#</option>
      </cfoutput>
    </select>
  </div>

  <div class="mb-3">
    <label for="countySelect" class="form-label">County</label>
    <select id="countySelect" class="form-select">
      <option value="">Select County</option>
    </select>
  </div>

  <div class="mb-3">
    <label for="fk_court" class="form-label">Court</label>
    <select id="fk_court" name="fk_court" class="form-select" >
      <option value="">Select Court</option>
    </select>
  </div>
</cfif>


  <div class="form-check mb-3">
    <input class="form-check-input" type="checkbox" id="update_external" name="update_external"
      <cfif case_mode EQ "new">checked</cfif>>
    <label class="form-check-label" for="update_external">
      Update externally
    </label>
  </div>

<div class="d-flex justify-content-between align-items-center mt-4">
  <!--- Left: Update Case --->
  <button type="submit" class="btn btn-primary">Update Case</button>
  
<cfoutput>
  <a style="color:white;" href="case_details.cfm?id=#getCase.id#" class="btn btn-danger">
    Cancel
  </a>
  </cfoutput>
</div>
      </form>
    </div>
  </div>
</div>


 
<div class="modal fade" id="updateSpinnerModal" tabindex="-1" role="dialog" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered" role="document">
    <div class="modal-content p-4 text-center">
      <div class="spinner-border text-primary" role="status">
        <span class="sr-only">Loading...</span>
      </div>
      <div class="mt-3">Synchronizing case data... please wait.</div>
    </div>
  </div>
</div>

<script>
$('#updateSpinnerModal').modal('show');
$.ajax({
  url: 'run_pacer_update.cfm',
  method: 'POST',
  data: { case_id: yourCaseId },
  success: function(response) {
    $('#updateSpinnerModal').modal('hide');
    // maybe show success toast
  },
  error: function() {
    $('#updateSpinnerModal').modal('hide');
    alert("Something went wrong. Please try again.");
  }
});
</script>
<script>
  // County array: [{id, name, state_code}]
  var counties = [
    <cfoutput query="getCounties">
      {id: '#id#', name: '#JSStringFormat(name)#', state_code: '#state_code#'}<cfif getCounties.currentRow LT getCounties.recordCount>,</cfif>
    </cfoutput>
  ];
  // Court array: [{id, display, county_id}]
  var courts = [
    <cfoutput query="getCourts">
      {id: '#id#', display: '#JSStringFormat(display)#', county_id: '#county_id#'}<cfif getCourts.currentRow LT getCourts.recordCount>,</cfif>
    </cfoutput>
  ];
</script>

<script>
  // Prefill for edit mode
  var initialCourtId = "<cfoutput>#getCase.fk_court#</cfoutput>";

  function filterCounties(stateCode) {
    $('#countySelect').empty().append('<option value="">Select County</option>');
    counties.filter(c => c.state_code === stateCode).forEach(function(c) {
      $('#countySelect').append(`<option value="${c.id}">${c.name}</option>`);
    });
    $('#countySelect').trigger('change');
  }

  function filterCourts(countyId) {
    $('#fk_court').empty().append('<option value="">Select Court</option>');
    courts.filter(c => c.county_id == countyId).forEach(function(c) {
      $('#fk_court').append(`<option value="${c.id}">${c.display}</option>`);
    });
    $('#fk_court').trigger('change');
  }

  // On state change, update counties
  $('#stateSelect').on('change', function() {
    filterCounties(this.value);
    $('#fk_court').empty().append('<option value="">Select Court</option>');
  });

  // On county change, update courts
  $('#countySelect').on('change', function() {
    filterCourts(this.value);
  });

  // Prefill if editing
  $(document).ready(function() {
    if (initialCourtId) {
      // Find the selected court's county/state
      var selectedCourt = courts.find(c => c.id == initialCourtId);
      if (selectedCourt) {
        var selectedCounty = counties.find(c => c.id == selectedCourt.county_id);
        if (selectedCounty) {
          $('#stateSelect').val(selectedCounty.state_code);
          filterCounties(selectedCounty.state_code);
          $('#countySelect').val(selectedCourt.county_id);
          filterCourts(selectedCourt.county_id);
          $('#fk_court').val(initialCourtId);
        }
      }
    }
  });
</script>
<cfinclude template="footer_script.cfm">
<script>
document.querySelector("form").addEventListener("submit", function(e) {
  const updateExternal = document.getElementById("update_external").checked;
  if (updateExternal) {
    $('#updateSpinnerModal').modal('show');
  }
});
</script>
</body>
</html>
