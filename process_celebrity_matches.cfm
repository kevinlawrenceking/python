<cfinclude template="includes/functions.cfm"> <!--- Helper functions for parsing --->

<!--- Fetch Cases That Haven't Been Reviewed --->
<cfquery name="cases" datasource="Reach">
    SELECT id, case_number, case_name 
    FROM docketwatch.dbo.cases 
    WHERE celebrity_reviewed = 0;
</cfquery>

<!--- Fetch Celebrity List --->
<cfquery name="celebrities" datasource="Reach">
    SELECT name FROM docketwatch.dbo.celebrities;
</cfquery>

<!--- Loop Through Cases --->
<cfloop query="cases">
    <cfset caseId = cases.id>
    <cfset caseNumber = cases.case_number>
    <cfset rawCaseName = cases.case_name>

    <!--- Normalize Case Name --->
    <cfset parsedCaseName = fncNormalizeCaseName(rawCaseName)>

    <!--- Loop Through Celebrities --->
    <cfset matchFound = false>
    <cfloop query="celebrities">
        <cfset celebName = celebrities.name>

        <!--- If all words in celebName exist in case name, consider a match --->
        <cfif fncIsMatch(parsedCaseName, celebName)>
            <cfset matchFound = true>

            <!--- Insert into Matches Table (Using Celebrity Name, Not ID) --->
<cfquery datasource="Reach">
INSERT INTO docketwatch.dbo.case_celebrity_matches (fk_case, fk_celebrity, match_status)
SELECT 
    c.id AS fk_case,
    p.id AS fk_celebrity,
    'POSSIBLE' AS match_status
FROM docketwatch.dbo.cases c
CROSS JOIN docketwatch.dbo.celebrities p
WHERE 
    p.name <> ''   
    AND p.name IS NOT NULL
    AND c.case_name LIKE '%' + p.name + '%'
    AND NOT EXISTS (   
        SELECT 1 
        FROM docketwatch.dbo.case_celebrity_matches cm 
        WHERE cm.fk_case = c.id AND cm.fk_celebrity = p.id
    );
</cfquery>


            <cfoutput>
                Match Found: #celebName# in Case #caseNumber# (#rawCaseName#)
            </cfoutput>
        </cfif>
    </cfloop>

    <!--- Mark Case as Reviewed --->
    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases 
        SET celebrity_reviewed = 1
        WHERE id = <cfqueryparam value="#caseId#" cfsqltype="cf_sql_integer">;
    </cfquery>

    <cfoutput>
        <br>Processed Case: #caseNumber# - #rawCaseName# (#parsedCaseName#) | Matched: #matchFound#
    </cfoutput>

</cfloop>

<cfoutput><br>Processing Complete!</cfoutput>
