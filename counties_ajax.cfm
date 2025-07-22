<cfquery name="getCounties" datasource="Reach">
    SELECT [id], [name], [code]
    FROM [docketwatch].[dbo].[counties]
</cfquery>

<!--- Create an array of county objects, using only the county name --->
<cfset countyList = []>
<cfloop query="getCounties">
    <cfset countyObj = { "name" = getCounties.name } >
    <cfset arrayAppend(countyList, countyObj)>
</cfloop>

<cfcontent type="application/json" reset="true">
<cfoutput>#serializeJSON(countyList)#</cfoutput>
