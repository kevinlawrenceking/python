<cfquery name="getCostSummary" datasource="reach">
    SELECT 
        CAST(created_at AS DATE) AS billing_date,
        SUM(cost) AS total_cost,
        SUM(pages) AS total_pages,
        COUNT(DISTINCT fk_case) AS total_cases
    FROM docketwatch.dbo.pacer_billing_history
    WHERE created_at >= DATEADD(DAY, -4, CAST(GETDATE() AS DATE))  <!--- Last 5 days including today --->
    GROUP BY CAST(created_at AS DATE)
    ORDER BY billing_date DESC
</cfquery>

<cfquery name="getTotalCost" datasource="reach">
    SELECT 
        SUM(cost) AS overall_cost,
        SUM(pages) AS overall_pages,
        COUNT(DISTINCT fk_case) AS overall_cases
    FROM docketwatch.dbo.pacer_billing_history
</cfquery>


<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Pacer Estimated Costs</title>
  <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">


<div class="container mt-5">
  <h2 class="mb-4">PACER Cost Summary (Last 5 Days)</h2>

  <table class="table table-bordered table-striped">
    <thead>
      <tr>
        <th>Date</th>
        <th>Total Cost</th>
        <th>Total Pages</th>
        <th>Total Cases</th>
      </tr>
    </thead>
    <tbody>
      <cfoutput query="getCostSummary">
        <tr>
          <td>#DateFormat(billing_date, "mmmm d, yyyy")#</td>
          <td>$#NumberFormat(total_cost, "9.99")#</td>
          <td>#total_pages#</td>
          <td>#total_cases#</td>
        </tr>
      </cfoutput>
    </tbody>
  </table>

  <h4 class="mt-4">Overall Total</h4>
  <ul>
    <li><strong>Total Cost:</strong> $<cfoutput>#NumberFormat(getTotalCost.overall_cost, "9.99")#</cfoutput></li>
    <li><strong>Total Pages:</strong> <cfoutput>#getTotalCost.overall_pages#</cfoutput></li>
    <li><strong>Total Unique Cases:</strong> <cfoutput>#getTotalCost.overall_cases#</cfoutput></li>
  </ul>
</div>





<cfinclude template="footer_script.cfm">

</body>
</html>
