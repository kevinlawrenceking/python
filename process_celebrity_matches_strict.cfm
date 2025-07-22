<cfcontent type="application/json">

<!--- Fetch Cases Needing Celebrity Check --->
<cfquery name="cases" datasource="Reach">
    SELECT id, case_number, case_name
    FROM docketwatch.dbo.cases
    WHERE celebrity_checked = 0
    ORDER BY id ASC
</cfquery>

<!--- Fetch Celebrities and Aliases (excluding ignored) --->
<cfquery name="celebrities" datasource="Reach">
SELECT 
    c.id AS fk_celebrity,
    COALESCE(a.name, c.name) AS celeb_name
FROM docketwatch.dbo.celebrities c
LEFT JOIN docketwatch.dbo.celebrity_names a
    ON a.fk_celebrity = c.id AND a.ignore != 1
WHERE c.ignore = 0
ORDER BY c.id;
</cfquery>

<!--- Fetch Case Parties for Each Case --->
<cfloop query="cases">
    <cfset caseID = cases.id>
    <cfset caseNumber = cases.case_number>
    <cfset caseName = cases.case_name>
    <cfset matchedCelebrities = []>

    <cfquery name="caseParties" datasource="Reach">
        SELECT party_name 
        FROM docketwatch.dbo.case_parties
        WHERE fk_case = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_varchar">
    </cfquery>


    <cfloop query="caseParties">
        <cfset partyName = caseParties.party_name>
        

        <cfloop query="celebrities">
            <cfset celebID = celebrities.fk_celebrity>
            <cfset celebName = celebrities.celeb_name>

            <!--- Direct Match --->
            <cfif partyName EQ celebName>
                <cfset match_status = "Review">
            <cfelseif findnocase(celebName, partyName)>
                <cfset match_status = "PARTIAL">
            <cfelse>
                <cfset match_status = "">
            </cfif>

            <cfif match_status NEQ "">
                <cfif NOT arrayFind(matchedCelebrities, celebID & "-" & match_status)>
                    <cfset arrayAppend(matchedCelebrities, celebName)>
                    
                    <cfquery datasource="Reach">
                        INSERT INTO docketwatch.dbo.case_celebrity_matches (fk_case, fk_celebrity, match_status)
                        SELECT 
                            <cfqueryparam value="#caseID#" cfsqltype="cf_sql_varchar">,
                            <cfqueryparam value="#celebID#" cfsqltype="cf_sql_varchar">,
                     -
                            <cfqueryparam value="#match_status#" cfsqltype="cf_sql_varchar">
                        WHERE NOT EXISTS (
                            SELECT 1 FROM docketwatch.dbo.case_celebrity_matches 
                            WHERE fk_case = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_varchar">
                              AND fk_celebrity = <cfqueryparam value="#celebID#" cfsqltype="cf_sql_varchar">
                              AND match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
                        )
                    </cfquery>
                </cfif>
            </cfif>
        </cfloop>
    </cfloop>

    <!--- Mark Case as Checked --->
    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases
        SET celebrity_checked = 1
        WHERE id = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_varchar">
    </cfquery>

    <!--- Log Results --->
    <cfoutput>
        Processed Case: #caseNumber#<br>
        Matches:<br>
        #arrayToList(matchedCelebrities, "<br>")#<br><br>
    </cfoutput>
</cfloop>

<cfoutput>{"status": "completed"}</cfoutput>
