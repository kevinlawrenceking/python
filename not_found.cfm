 <cfquery name="getNotFoundCases" datasource="reach">
SELECT 
    c.[id],
    c.[case_number],
    c.[case_name],
    c.[case_url] AS external_url,
    'case_details.cfm?id=' + CAST(c.id AS VARCHAR(20)) AS internal_url,
    t.[tool_name],
    c.[not_found_count],
    c.[last_not_found],
    c.[last_found]
FROM [docketwatch].[dbo].[cases] c
INNER JOIN [docketwatch].[dbo].[tools] t ON t.id = c.fk_tool
WHERE c.not_found_count <> 0
ORDER BY c.last_not_found DESC
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Cases Not Found</title>
  <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">

<Script>
document.addEventListener("DOMContentLoaded", function() {
  var hash = window.location.hash;
  if (hash) {
    var row = document.querySelector(hash);
    if (row) {
      row.style.transition = "background-color 0.4s";
      row.style.backgroundColor = "#ffeeba";
      row.scrollIntoView({behavior: "smooth", block: "center"});
      // Flash effect
      setTimeout(function() { row.style.backgroundColor = ""; }, 1500);
      setTimeout(function() { row.style.backgroundColor = "#ffeeba"; }, 1800);
      setTimeout(function() { row.style.backgroundColor = ""; }, 2100);
    }
  }
});
</script>


<div class="container mt-5">
  <h2 class="mb-4">Cases Not Found</h2>
<p>This table shows cases that weren't found on the last scraping.  Once a case is found, it is removed from the list.</p>
  <table class="table table-bordered table-striped">
    <thead>
      <tr>
        <th>Case Number</th>
        <th>Case Name</th>
        <th>Tool</th>
        <th>Count</th>
        <th>Last Not Found</th>
        <th>Last Found</th>
        <th>External Link</th>
        <th>Internal Link</th>
      </tr>
    </thead>
    <tbody>
      <cfoutput query="getNotFoundCases">
        <tr id="case#id#">
          <td nowrap>#case_number#</td>
          <td>#case_name#</td>
          <td nowrap>#tool_name#</td>
          <td nowrap>#not_found_count#</td>
          <td nowrap>
            <cfif last_not_found IS NOT "">
              #DateFormat(last_not_found, "MM-dd-YY")# #TimeFormat(last_not_found, "h:mm:ss tt")#
            <cfelse>
              &mdash;
            </cfif>
          </td>
          <td nowrap>
            <cfif last_found IS NOT "">
              #DateFormat(last_found, "MM-dd-YY")# #TimeFormat(last_found, "h:mm:ss tt")#
            <cfelse>
              &mdash;
            </cfif>
          </td>
          <td nowrap>
            <cfif external_url IS NOT "">
              <a href="#external_url#" target="_blank">#left(external_url,29)#</a>
            <cfelse>
              &mdash;
            </cfif>
          </td>
          <td nowrap>
            <a href="#internal_url#">DocketWatch</a>
          </td>
        </tr>
      </cfoutput>
    </tbody>
  </table>
</div>




<cfinclude template="footer_script.cfm">

</body>
</html>
