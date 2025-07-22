


<!--- Query cases without tool_case_id --->
<cfquery name="casesWithoutToolCase" datasource="Reach" >
    SELECT c.id, c.case_number, t.*, ac.*
    FROM docketwatch.dbo.cases c,docketwatch.dbo.tools t
	inner join docketwatch.dbo.api_calls ac on ac.fk_tool = t.id
    WHERE ac.fk_api_call_master = 5 and c.id NOT IN (SELECT fk_case FROM docketwatch.dbo.cases)
;
</cfquery>

<!--- Query all cases with related tool/api_calls info, filtered as needed --->
<cfquery name="casesWithApiCall" datasource="Reach">
    SELECT 
        c.id, 
        c.case_number, 
        t.*, 
        ac.*
    FROM 
        docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.tools t ON c.fk_tool = t.id
    INNER JOIN docketwatch.dbo.api_calls ac ON ac.fk_tool = t.id
    WHERE 
        ac.fk_api_call_master = 5
</cfquery>

<cfloop query="casesWithoutToolCase">
    <cfset case_number = casesWithoutToolCase.case_number>
    <cfset id = casesWithoutToolCase.case_number>
    <cfset api_key = casesWithoutToolCase.api_key>
    

    <!--- Construct API URL --->
<cfset api_url = api_base_url & api_endpoint & request_params>
<cfset api_url = Replace(api_url, "##case_number##", case_number, "all")>
<Cfoutput>api_url:#api_url#</cfoutput><BR><Cfoutput>api_key:#api_key#<BR></cfoutput>


    <!--- Make API Call --->
    <cfhttp url="#api_url#" method="GET">
   <cfhttpparam type="header" name="Authorization" value="Bearer #api_key#">
    </cfhttp>

    <!--- Parse API Response --->
    <cfset jsonResponse = DeserializeJSON(cfhttp.fileContent)>
    <p><cfoutput><Cfdump var="#jsonREsponse#"><BR>api_url: #api_url#
</cfoutput>

 
 <!--- Check if API returned results --->
    <cfif StructKeyExists(jsonResponse, "caseSearchResultArray") AND ArrayLen(jsonResponse.caseSearchResultArray) GT 0>
        
        <!--- Loop through each returned case result and insert them into tool_cases --->
        <cfloop from="1" to="#ArrayLen(jsonResponse.caseSearchResultArray)#" index="i">
            <cfset tool_case_id = jsonResponse.caseSearchResultArray[i].caseId>
            <cfset tool_case_name = jsonResponse.caseSearchResultArray[i].caseName>
            <cfset tool_case_number = jsonResponse.caseSearchResultArray[i].caseNumber>

            <!--- Insert each returned case into tool_cases table 
            <cfquery datasource="Reach">
                INSERT INTO docketwatch.dbo.tool_cases (fk_case, fk_tool, tool_case_id, tool_case_name, tool_case_number, last_updated)
                VALUES (
                    <cfqueryparam value="#id#" cfsqltype="cf_sql_integer">,
                    <cfqueryparam value="1" cfsqltype="cf_sql_integer">,  
                    <cfqueryparam value="#tool_case_id#" cfsqltype="cf_sql_varchar">,
                    <cfqueryparam value="#tool_case_name#" cfsqltype="cf_sql_varchar">,
                    <cfqueryparam value="#tool_case_number#" cfsqltype="cf_sql_varchar">,
                    <cfqueryparam value="#Now()#" cfsqltype="cf_sql_timestamp">
                )
            </cfquery>
 
            <cfoutput>
                <p> Case #case_number# Inserted Tool Case ID: #tool_case_id# (Name: #tool_case_name#, Number: #tool_case_number#)</p>
            </cfoutput> --->
        </cfloop>

    <cfelse>
        <cfoutput>
            <p> No matching case found in UniCourt for Case #case_number#</p>
        </cfoutput>
    </cfif>

</cfloop>