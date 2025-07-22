<cfcontent type="application/json">

<!--- Function to Convert to Proper Case --->
<cffunction name="toProperCase" returntype="string">
    <cfargument name="inputString" type="string" required="true">
    <cfset var words = listToArray(arguments.inputString, " ")>
    <cfset var formattedString = "">

    <cfloop array="#words#" index="word">
        <cfif len(word) GT 0>
            <cfset word = ucase(left(word, 1)) & lcase(mid(word, 2, len(word)))>
            <!--- Capitalize after apostrophe & hyphen --->
            <cfset word = rereplaceNoCase(word, "(\w)'(\w)", "\1'\u\2", "all")>
            <cfset word = rereplaceNoCase(word, "(\w)-(\w)", "\1-\u\2", "all")>
            <cfset formattedString &= word & " ">
        </cfif>
    </cfloop>

    <cfreturn trim(formattedString)>
</cffunction>

<!--- Function to Convert "Last, First Middle" to "First Middle Last" --->
<cffunction name="convertLastFirstToProper" returntype="string">
    <cfargument name="name" type="string" required="true">
    
    <!--- Check if the name contains a comma --->  
    <cfif find(",", arguments.name)>
        <cfset var nameParts = listToArray(arguments.name, ",")>
        <cfset var lastName = trim(nameParts[1])>
        <cfset var firstMiddle = "">

        <!--- Handle middle names correctly --->  
        <cfif arrayLen(nameParts) GTE 2>
            <cfset firstMiddle = trim(nameParts[2])>
        </cfif>

        <!--- Format as "First Middle Last" --->  
        <cfset var formattedName = trim(toProperCase(firstMiddle) & " " & toProperCase(lastName))>

        <cfreturn formattedName>
    </cfif>

    <cfreturn arguments.name> <!--- Return unchanged if no comma --->
</cffunction>

<!--- Function to Clean Case Name --->  
<cffunction name="cleanCaseName" returntype="string">
    <cfargument name="caseName" type="string" required="true">
    <cfset var cleanedName = trim(caseName)>

    <!--- Remove Largest Phrases First --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Approval Of Minor'S Contract - ", "", "all")>
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Joint Petition Of:", "", "all")>
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Trust, Dated.*", "", "all")>
    <cfset cleanedName = rereplaceNoCase(cleanedName, "As Amended", "", "all")> <!--- New Rule --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Revocable Living Trust|Family Trust|Irrevocable Trust|Living Trust", "", "all")>

    <!--- Remove Medium-Length Phrases --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Dated [A-Za-z]+ [0-9]+,", "", "all")> <!--- Fix Dated X Issue --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, " ?- ?(CONSERVATORSHIP|DECEDENT|GUARDIANSHIP|IN THE MATTER OF|MINOR'S COMPROMISE)", "", "all")>
    <cfset cleanedName = rereplaceNoCase(cleanedName, " APPROVAL OF MINOR'S CONTRACT -", "", "all")>

    <!--- Remove "The " ONLY if it is at the beginning --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "^The\s+", "", "one")>

    <!--- Remove trailing "Trust" if it still exists --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*Trust$", "", "one")>

    <!--- Remove All Numbers and Slashes --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "[0-9/]", "", "all")>

    <!--- Fix Formatting Issues --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+,", ",", "all")> <!--- Fix " ," issue --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+", " ", "all")> <!--- Remove Extra Spaces --->  

    <!--- Final Trim --->  
    <cfreturn trim(cleanedName)>
</cffunction>

<!--- Query to Fetch Cases Where case_parties_checked = 0 --->  
<cfquery name="cases" datasource="Reach">
    SELECT id, case_number, case_name
    FROM docketwatch.dbo.cases
    WHERE case_parties_checked = 0
    ORDER BY id ASC
</cfquery>

<!--- Process Each Case --->  
<cfloop query="cases">
    <cfset caseID = cases.id>
    <cfset caseNumber = cases.case_number>
    <cfset caseName = cleanCaseName(cases.case_name)>

    <cfset parsedParties = []>

    <!--- Normalize Delimiters: Convert " VS ", " VS. ", and " AND " to "|" --->  
    <cfset normalizedCaseName = rereplaceNoCase(caseName, "\s(VS\.?|AND)\s", "|", "all")>

    <!--- Split the Case Name into Individual Parties --->  
    <cfset parties = listToArray(normalizedCaseName, "|")>

    <!--- Process Each Party Name --->  
    <cfloop array="#parties#" index="party">
        <cfset party = trim(party)>
        <cfset party = convertLastFirstToProper(party)> <!--- Fix Last, First Middle format --->  
        <cfset party = cleanCaseName(party)> <!--- Run cleaning AGAIN to catch leftovers --->  

        <!--- Prevent Duplicate Entries --->  
        <cfif NOT arrayFind(parsedParties, party)>
            <cfset arrayAppend(parsedParties, party)>
        </cfif>
    </cfloop>

    <!--- Insert Each Party Into `case_parties` Table --->  
    <cfloop array="#parsedParties#" index="finalParty">
        <cfquery datasource="Reach">
            INSERT INTO docketwatch.dbo.case_parties (fk_case, party_name, party_role)
            SELECT 
                <cfqueryparam value="#caseID#" cfsqltype="cf_sql_integer">,
                <cfqueryparam value="#finalParty#" cfsqltype="cf_sql_varchar">,
                'Party'
            WHERE NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.case_parties 
                WHERE fk_case = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_integer">
                AND party_name = <cfqueryparam value="#finalParty#" cfsqltype="cf_sql_varchar">
            )
        </cfquery>
    </cfloop>

    <!--- Mark Case as Checked (case_parties_checked = 1) --->  
    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases
        SET case_parties_checked = 1
        WHERE id = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_integer">
    </cfquery>

    <!--- Log Processed Case --->  
    <cfoutput>
        Processed Case: #caseNumber# - #caseName#<br>
        Parties Inserted:<br>
        #arrayToList(parsedParties, "<br>")#<br><br>
    </cfoutput>

</cfloop>

<!--- Query to Fetch Case Parties to Clean --->
<cfquery name="parties" datasource="Reach">
    SELECT id, party_name
    FROM docketwatch.dbo.case_parties
</cfquery>

<!--- Process Each Party --->
<cfloop query="parties">
    <cfset partyID = parties.id>
    <cfset partyName = parties.party_name>

    <!--- Apply Cleanup Rules --->  
    <cfset cleanedName = trim(partyName)>

     
    <cfset cleanedName = rereplaceNoCase(cleanedName, "APPROVAL OF MINOR'S CONTRACT -", "", "all")>

    <!--- Remove "Joint Petition Of:" --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Joint Petition Of:", "", "all")>
<cfset cleanedName = rereplaceNoCase(cleanedName, "LIVING TRUST DATED", "", "all")>
    

        <cfset cleanedName = rereplaceNoCase(cleanedName, "REVOCABLE LIVING TRUST", "", "all")>
        <cfset cleanedName = rereplaceNoCase(cleanedName, "SPECIAL NEEDS TRUST", "", "all")>
    <!--- Remove "Approval Of Minor'S Contract - " --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Approval Of Minor'S Contract - ", "", "all")>
 <cfset cleanedName = rereplaceNoCase(cleanedName, "Family Trust", "", "all")>
 <cfset cleanedName = rereplaceNoCase(cleanedName, "Living Trust", "", "all")>
 <cfset cleanedName = rereplaceNoCase(cleanedName, "trust udt", "", "all")>
<!--- Array of Full Month Names --->
<cfset months = ["inter vivos","a minor marriage of","special needs","revocable","Trust April","TRUST JUNE","January", "February", "March", "July", "August", "September", "October", "November", "December","TRUST UDT","LIVING TRUST","FAMILY TRUST","REVOCABLE TRUST","TRUST "]>

<!--- Loop Through Each Month and Remove It From cleanedName --->
<cfloop array="#months#" index="month">
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\b" & month & "\b", "", "all")>
</cfloop>

 <cfset cleanedName = rereplaceNoCase(cleanedName, "SUBTRUSTS CREATED THEREUNDER", "", "all")>

 <cfset cleanedName = rereplaceNoCase(cleanedName, " LIVING", "", "all")>
    <!--- Remove "Dated June " --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "Dated June ", "", "all")>

    <!--- Remove "Trust, Dated" and everything after --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*Trust, Dated.*", "", "all")>

    <!--- Remove "The " if it appears at the beginning --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "^The\s+", "", "one")>

    <!--- Remove "Revocable Living Trust", "Family Trust", and "Irrevocable Trust" --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*(Revocable Living Trust|Family Trust|Irrevocable Trust)", "", "all")>

    <!--- Remove all numbers and slashes --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "[0-9/]", "", "all")>

    <!--- Remove trailing "Trust" if it still exists --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*Trust$", "", "one")>

    <!--- Fix formatting issue: Change " ," to "," --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+,", ",", "all")>
 <cfset cleanedName = rereplaceNoCase(cleanedName, "Dated", "", "all")>
  <cfset cleanedName = rereplaceNoCase(cleanedName, " inc ", "", "all")>

      <!--- Fix Formatting Issues --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+,", ",", "all")> <!--- Fix " ," issue --->  
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+", " ", "all")> <!--- Remove Extra Spaces --->  

    <!--- Final Trim --->  
    <cfset cleanedName = trim(cleanedName)>

    <!--- Update if the Name Changed --->  
    <cfif cleanedName NEQ partyName>
        <cfquery datasource="Reach">
            UPDATE docketwatch.dbo.case_parties
            SET party_name = <cfqueryparam value="#cleanedName#" cfsqltype="cf_sql_varchar">
            WHERE id = <cfqueryparam value="#partyID#" cfsqltype="cf_sql_char">
        </cfquery>

        <!--- Log Changes --->  
        <cfoutput>
            Updated Party: #partyName# → #cleanedName#<br>
        </cfoutput>
    </cfif>
</cfloop>

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

    <!--- Loop Through Case Parties --->
    <cfloop query="caseParties">
        <cfset partyName = caseParties.party_name>
        
        <!--- Loop Through Celebrities to Find Matches --->
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


</cfloop>





<cfoutput>{"status": "completed"}</cfoutput>
