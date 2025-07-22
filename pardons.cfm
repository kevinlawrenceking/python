<cfquery name="getPardons" datasource="reach">
SELECT 
  p.[pardon_date],
  c.[name] as celebrity_name,
  p.[name] as pardon_name,
  p.[district],
  p.[sentenced],
  p.[offense],
  p.[link],
  CASE 
    WHEN c.fk_celebrity IS NOT NULL 
      THEN 'celebrity_details.cfm?id=' + CAST(c.fk_celebrity AS varchar(36)) 
    ELSE NULL 
  END AS celebrity_url
FROM [docketwatch].[dbo].[pardons] p
LEFT JOIN [docketwatch].[dbo].[celebrity_names] c 
  ON c.name = p.name
ORDER BY p.[pardon_date] DESC, p.[name]
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Presidential Pardons</title>
  <cfinclude template="head.cfm">
  <style>
    .pdf-link { color: #d9534f; font-size: 1.3em; }
    .celeb-link { color: #337ab7; margin-left: 5px; font-size: 1em; }
  </style>
</head>
<body>
<cfinclude template="navbar.cfm">

<div class="container mt-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Presidential Pardons</h2>
  </div>
  <table id="pardonsTable" class="table table-striped table-bordered w-100">
    <thead class="table-dark">
      <tr>
        <th>Date</th>
        <th>Name</th>
        <th>District</th>
        <th>Sentence</th>
        <th>Offense</th>
        <th>PDF</th>
      </tr>
    </thead>
    <tbody>
      <cfloop query="getPardons">
      <cfoutput>
        <tr>
          <td nowrap>#dateFormat(getPardons.pardon_date, "yyyy-mm-dd")#</td>
          <td class="nowrap">
            <!--- Prefer celebrity_name, fallback to pardon_name --->
            #htmlEditFormat(getPardons.pardon_name)#
            <cfif len(getPardons.celebrity_url)>
              <a href="#getPardons.celebrity_url#" title="View Details" class="celeb-link" target="_blank">
                <i class="fa-solid fa-up-right-from-square"></i>
              </a>
            </cfif>
          </td>
          <td>#htmlEditFormat(getPardons.district)#</td>
          <td>#htmlEditFormat(getPardons.sentenced)#</td>
          <td>#htmlEditFormat(getPardons.offense)#</td>
          <td class="text-center">
            <cfif len(getPardons.link)>
              <a href="#getPardons.link#" class="pdf-link" target="_blank" title="View PDF">
                <i class="fa fa-file-pdf"></i>
              </a>
            </cfif>
          </td>
        </tr>
      </cfoutput>
      </cfloop>
    </tbody>
  </table>
</div>

<cfinclude template="footer_script.cfm">

<script>
$(document).ready(function () {
  $('#pardonsTable').DataTable({
    order: [[0, 'desc']],
    paging: true,
    searching: true,
    ordering: true,
    info: true,
    pageLength: 50,
    lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]]
  });
});
</script>
</body>
</html>
