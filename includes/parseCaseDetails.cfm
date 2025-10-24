<cffunction name="parseCaseDetails" returntype="struct">
    <cfargument name="content" type="string">

    <cfset caseDetails = structNew()>
    <cfset caseDetails.caseNumber = "">
    <cfset caseDetails.caseName = "">
    <cfset caseDetails.notes = "">

    <!--- Regex to Extract Case Details (Case-Insensitive) --->
    <cfif REFindNoCase('<b>Case Number:</b>&nbsp;&nbsp;(\d+\w+\d+)', arguments.content)>
        <cfset caseDetails.caseNumber = REMatch('<b>Case Number:</b>&nbsp;&nbsp;(\d+\w+\d+)', arguments.content)[1]>
    </cfif>
    
    <cfif REFindNoCase('<b>Case Type:</b>&nbsp;&nbsp;(.+?)<br>', arguments.content)>
        <cfset caseDetails.notes = REMatch('<b>Case Type:</b>&nbsp;&nbsp;(.+?)<br>', arguments.content)[1]>
    </cfif>

    <cfif REFindNoCase('<b>Case Number:</b>&nbsp;&nbsp;.*?<br>(.*?)<div', arguments.content)>
        <cfset caseDetails.caseName = REMatch('<b>Case Number:</b>&nbsp;&nbsp;.*?<br>(.*?)<div', arguments.content)[1]>
    </cfif>

    <cfreturn caseDetails>
</cffunction>
