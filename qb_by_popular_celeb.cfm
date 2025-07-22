<!--- Query to Get Top 100 Celebrities --->
<cfquery name="topCelebs" datasource="Reach">
    EXEC damz.dbo.Get_Top_Celebrities @start_date = <cfqueryparam value="#DateFormat(DateAdd('yyyy', -1, Now()), 'yyyy-mm-dd')#" cfsqltype="cf_sql_date">
</cfquery>

<!--- Set Batch Size Limit --->
<cfset batchSize = 15>
<cfset celebNames = []>

<!--- Store Celebrity Names in an Array --->
<cfloop query="topCelebs">
    <cfset ArrayAppend(celebNames, topCelebs.celebrity_name)>
</cfloop>

<!--- Loop Through Celebrities in Batches of 15 --->
<cfset totalBatches = Ceiling(ArrayLen(celebNames) / batchSize)>
<cfset allResults = []>
<Cfset api_key = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl9pZCI6IlRLSUQ4bVg2N2FmOWI2YjlXMyIsImNsaWVudF9pZCI6ImdNa0hva0o3clEzV2Z1WTlrbVpGUm1kblVSNUhxcUpaIiwidWNhX2FjY291bnRfaWQiOiJwMTczOTE2MzEzMiIsImF1ZCI6Imh0dHBzOi8vZW50ZXJwcmlzZWFwaS51bmljb3VydC5jb20iLCJpc3MiOiJodHRwczovL3VuaWNvdXJ0LmNvbSIsInN1YiI6IkVOVEVSUFJJU0VfQVBJX0NSRURFTlRJQUxTIiwiZ3R5IjoiQ2xpZW50X0NyZWRlbnRhaWxzIiwiaWF0IjoxNzM5NTYxODM1LCJleHAiOjQ4OTUzMjE4MzV9.rZ0ahmz3N-l-Ol527FSLP89ralsnMreZzP7wHd3RUNzbaQg8M4gTJhvECou3jbvrPtoJzl-4z-WSgaTl30vbbvQlAZO-h3D0aj3CyW_04MCvJm-AltO7cOdFT6F8ZqPx1nQFww1MwD-ZikIpAyIpMJhsUnmumoMOr5HmVwwprE7zVaMYqP6U9rx1ci91flaYbUVWEWKviJH7bigCZ6mRmBv-zZY3SFm-CQ1GPy1yCXg2rFq5GhNb2g5uoeYw9wjwm3_cOf7KcIJKOcZU-egpppeviyRoLDYsLsfiyxdm6k6eTxab5hldaZhqFCgwZ5EShridUMIVWtoiRjL8Cb7a_w" />
<cfloop from="1" to="#totalBatches#" index="batchNum">
    <cfset batchQuery = 'Party:(name:('>

    <!--- Loop Through Each Batch --->
    <cfset startIndex = ((batchNum - 1) * batchSize) + 1>
    <cfset endIndex = Min(batchNum * batchSize, ArrayLen(celebNames))>

    <cfloop from="#startIndex#" to="#endIndex#" index="i">
        <cfset batchQuery = batchQuery & '"' & celebNames[i] & '"'>

        <!--- Add " OR " if not the last item --->
        <cfif i LT endIndex>
            <cfset batchQuery = batchQuery & ' OR '>
        </cfif>
    </cfloop>

    <cfset batchQuery = batchQuery & '))'>

    <!--- Encode the query --->
    <cfset encodedQuery = URLEncodedFormat(batchQuery)>

    <!--- Construct API URL --->
    <cfset api_url = "https://enterpriseapi.unicourt.com/caseSearch?q=" & encodedQuery>

    <!--- Debug Output (Remove in Production) --->
    <cfoutput>
        <p>Batch #batchNum# API URL: #api_url#</p>
    </cfoutput>

    <!--- Make API Call --->
    <cfhttp url="#api_url#" method="GET" result="apiResponse">
        <cfhttpparam type="header" name="Authorization" value="Bearer #api_key#">
    </cfhttp>

    <!--- Parse API Response --->
    <cfset jsonResponse = DeserializeJSON(apiResponse.fileContent)>

    <!--- Store Results from Each Batch --->
    <cfif StructKeyExists(jsonResponse, "caseSearchResultArray")>
        <cfset ArrayAppend(allResults, jsonResponse.caseSearchResultArray)>
    </cfif>
</cfloop>

<!--- Output Final Combined Results --->
<cfoutput>
    <p>Total API Calls: #totalBatches#</p>
    <p>Combined Case Results: #SerializeJSON(allResults)#</p>
</cfoutput>
