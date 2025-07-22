<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Add Case</title>
  <cfinclude template="head.cfm">
</head>
<body>
<cfinclude template="navbar.cfm">

<div class="container mt-5">
  <h2 class="mb-4">Add New Case</h2>
  
  <cfoutput>
  <form method="post" action="add_case2.cfm">
    <cfquery name="getTools" datasource="Reach">
      SELECT id, tool_name FROM docketwatch.dbo.tools ORDER BY tool_name
    </cfquery>

    <div class="mb-3">
      <label for="tool" class="form-label">Tool</label>
      <select name="tool" id="tool" class="form-select" required>
        <cfloop query="getTools">
          <option value="#id#">#tool_name#</option>
        </cfloop>
      </select>
    </div>

    <div class="mb-3">
      <label for="new_casename" class="form-label">Case Name</label>
      <input type="text" id="new_casename" name="new_casename" class="form-control" required />
    </div>

    <div class="mb-3">
      <label for="new_caseNumber" class="form-label">Case Number</label>
      <input type="text" id="new_caseNumber" name="new_caseNumber" class="form-control" required />
    </div>

    <div class="mb-3">
      <label for="new_caseUrl" class="form-label">Case URL</label>
      <input type="text" id="new_caseUrl" name="new_caseUrl" class="form-control" required />
    </div>

    <button type="submit" class="btn btn-primary">Add Case</button>
  </form>
  </cfoutput>
</div>

<cfinclude template="footer_script.cfm">
</body>
</html>
