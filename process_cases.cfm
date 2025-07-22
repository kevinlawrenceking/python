<Cfset dbug = "N">

<cfif dbug eq "N">
<cfcontent type="application/json">
</cfif>
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

      <!--- Define the cleaning function --->
        <cffunction name="cleanCaseName" returntype="string" output="false">
            <cfargument name="caseName" type="string" required="true">
            <cfargument name="code" type="string" required="true">
            <cfset var cleanedName = trim(arguments.caseName)>
            
            <cfif arguments.code eq "LAC">
                <!--- LAC: perform all standard find/replace operations --->
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Approval Of Minor'S Contract - ", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "APPROVAL OF MINOR'S CONTRACT -", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Joint Petition Of:", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "LIVING TRUST DATED", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "REVOCABLE LIVING TRUST", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "SPECIAL NEEDS TRUST", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Revocable Living Trust|Family Trust|Irrevocable Trust|Living Trust", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Family Trust", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Living Trust", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "trust udt", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Dated [A-Za-z]+ [0-9]+,", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, " ?- ?(CONSERVATORSHIP|DECEDENT|GUARDIANSHIP|IN THE MATTER OF|MINOR'S COMPROMISE)", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, " APPROVAL OF MINOR'S CONTRACT -", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "SUBTRUSTS CREATED THEREUNDER", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Dated June ", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, " inc ", "", "all")>
                <!--- Remove full month names and related terms --->
                <cfset months = ["inter vivos","a minor marriage of","special needs","revocable","Trust April","TRUST JUNE","January", "February", "March", "July", "August", "September", "October", "November", "December","TRUST UDT","LIVING TRUST","FAMILY TRUST","REVOCABLE TRUST","TRUST "]>
                <cfloop array="#months#" index="month">
                    <cfset cleanedName = rereplaceNoCase(cleanedName, "\b" & month & "\b", "", "all")>
                </cfloop>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*Trust, Dated.*", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*(Revocable Living Trust|Family Trust|Irrevocable Trust)", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "^The\s+", "", "one")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\s*Trust$", "", "one")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "[0-9/]", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+,", ",", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+", " ", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "Dated", "", "all")>
            
            <cfelseif arguments.code eq "NYC">
                <!--- NYC: Remove extraneous jurisdiction/procedural phrases and replace party separator --->
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(et al\.?)\b", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(the people of the state of new york)\b", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(state of new york)\b", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(the city of new york)\b", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(city of new york)\b", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(county of [A-Z ]+)\b", "", "all")>
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\b(in re|ex parte)\b", "", "all")>
                <!--- Remove descriptive phrases --->
                <cfset cleanedName = rereplaceNoCase(cleanedName, "an infant under the age of [0-9]+ years by his father and natural guardian,", "", "all")>
                <!--- Remove d/b/a phrases --->
                <cfset cleanedName = rereplaceNoCase(cleanedName, "d/b/a\s+[A-Z0-9 ]+", "", "all")>
                <!--- Replace the party separator " v. " (or "v") with a pipe --->
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\sv\.?\s", " | ", "all")>
                <!--- Clean up extra spaces --->
                <cfset cleanedName = rereplaceNoCase(cleanedName, "\s+", " ", "all")>
                <cfset cleanedName = trim(cleanedName)>
            
            <cfelse>
                <!--- Default behavior if county is not recognized --->
            </cfif>
            
            <cfreturn trim(cleanedName)>
        </cffunction>
<!--- Query to Fetch Cases Where case_parties_checked = 0 --->  

<!--- Query to Fetch Cases --->
<cfquery name="cases" datasource="Reach">
    SELECT c.id, c.case_number, c.case_name, t.name AS county_name, t.code
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts o ON c.fk_court = o.court_code
    INNER JOIN docketwatch.dbo.counties t ON o.fk_county = t.id 
    WHERE c.case_parties_checked = 0
    ORDER BY c.id ASC
</cfquery>

<!--- Initialize Totals --->
<cfset totalCases = 0>
<cfset totalPartiesFound = 0>
<cfset totalUniqueParties = 0>

<!--- Process Each Case --->
<cfloop query="cases">
    <!--- Increment total cases counter --->
    <cfset totalCases = totalCases + 1>
    
    <cfset caseID = cases.id />
    <cfset caseNumber = cases.case_number />
    <cfset code = TRIM(cases.code)>
    <cfset caseName = cleanCaseName(cases.case_name, code) />
    <cfset parsedParties = []>

    <!--- Normalize Delimiters: Convert " VS ", " VS. ", and " AND " to "|" --->
    <cfif code eq "LAC">
        <cfset normalizedCaseName = rereplaceNoCase(caseName, "\s(VS\.?|AND)\s", "|", "all")>
    <cfelseif code eq "NYC">
        <cfset normalizedCaseName = rereplaceNoCase(caseName, "\sv\.?\s", "|", "all")>
    </cfif>

    <!--- Split the Case Name into Individual Parties --->
    <cfset parties = listToArray(normalizedCaseName, "|")>
    <!--- Count the total parties found (including duplicates) --->
    <cfset partiesFound = arrayLen(parties)>
    <cfset totalPartiesFound = totalPartiesFound + partiesFound>

    <!--- Process Each Party Name --->
    <cfloop array="#parties#" index="party">
        <cfset party = trim(party)>
        <cfif code eq "LAC">
            <cfset party = convertLastFirstToProper(party)> <!--- Fix Last, First Middle format --->
        </cfif>
        <!--- Prevent Duplicate Entries --->
        <cfif NOT arrayFind(parsedParties, party)>
            <cfset arrayAppend(parsedParties, party)>
        </cfif>
    </cfloop>
    
    <!--- Count unique parties for this case --->
    <cfset uniqueParties = arrayLen(parsedParties)>
    <cfset totalUniqueParties = totalUniqueParties + uniqueParties>

    <!--- Insert Each Party Into case_parties Table --->
    <cfloop array="#parsedParties#" index="finalParty">
        <cfquery datasource="Reach">
            INSERT INTO docketwatch.dbo.case_parties (fk_case, party_name, party_role)
            SELECT 
                <cfqueryparam value="#caseID#" cfsqltype="cf_sql_integer">,
                <cfqueryparam value="#finalParty#" maxLength="500" cfsqltype="cf_sql_varchar">,
                'Party'
            WHERE NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.case_parties 
                WHERE fk_case = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_integer">
                  AND party_name = <cfqueryparam value="#finalParty#" maxLength="500" cfsqltype="cf_sql_varchar">
            )
        </cfquery>
    </cfloop>

    <!--- Mark Case as Checked (case_parties_checked = 1) --->
    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases
        SET case_parties_checked = 1
        WHERE id = <cfqueryparam value="#caseID#" cfsqltype="cf_sql_integer">
    </cfquery>
</cfloop>

<!--- Log Totals After Processing --->
<cfquery datasource="Reach">
    INSERT INTO docketwatch.dbo.task_log (created_at, task_name, source, status, details)
    VALUES (GETDATE(), 'Process Cases - Party Processing', 'process_cases.cfm', 'Completed',
            'Total Cases Processed: #totalCases#, Total Parties Found: #totalPartiesFound#, Total Unique Parties: #totalUniqueParties#')
</cfquery>




<!--- Initialize counters for party cleanup --->
<cfset totalParties = 0>
<cfset partiesUpdated = 0>

<!--- Query to Fetch Case Parties to Clean --->
<cfquery name="parties" datasource="Reach">
    SELECT id, party_name
    FROM docketwatch.dbo.case_parties
</cfquery>

<!--- Process Each Party --->
<cfloop query="parties">
    <cfset totalParties = totalParties + 1>
    <cfset partyID = parties.id>
    <cfset partyName = parties.party_name>

    <!--- Apply Cleanup Rules --->
    <cfset cleanedName = trim(partyName)>

    <!--- Final Trim --->
    <cfset cleanedName = trim(cleanedName)>

    <!--- Update if the Name Changed --->
    <cfif cleanedName NEQ partyName>
        <cfquery datasource="Reach">
            UPDATE docketwatch.dbo.case_parties
            SET party_name = <cfqueryparam value="#cleanedName#" cfsqltype="cf_sql_varchar">
            WHERE id = <cfqueryparam value="#partyID#" cfsqltype="cf_sql_char">
        </cfquery>
        <cfset partiesUpdated = partiesUpdated + 1>
    </cfif>
</cfloop>

<!--- Log Totals After Cleanup --->
<cfquery datasource="Reach">
    INSERT INTO docketwatch.dbo.task_log (created_at, task_name, source, status, details)
    VALUES (GETDATE(), 'Clean Case Parties', 'process_cases.cfm - Cleanup', 'Completed',
            'Total Parties Processed: #totalParties#, Parties Updated: #partiesUpdated#')
</cfquery>






<cfquery datasource="Reach" name="insertCelebMatches" result="insResult">
    INSERT INTO docketwatch.dbo.case_celebrity_matches (fk_case, fk_celebrity, celebrity_name, match_status)
    SELECT c.id, ce.id, ce.name, 'Review'
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.case_parties p 
        ON p.fk_case = c.id
    INNER JOIN docketwatch.dbo.celebrities ce 
        ON ce.name = p.party_name
    WHERE NOT EXISTS (
        SELECT 1 
        FROM docketwatch.dbo.case_celebrity_matches m
        WHERE m.fk_case = c.id 
          AND m.fk_celebrity = ce.id
    )
    UNION
    SELECT c.id, ce.id, ce.name, 'Review'
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.case_parties p 
        ON p.fk_case = c.id
    INNER JOIN docketwatch.dbo.celebrity_names ca 
        ON ca.name = p.party_name 
           AND ca.ignore = 0
    INNER JOIN docketwatch.dbo.celebrities ce 
        ON ce.id = ca.fk_celebrity
    WHERE NOT EXISTS (
        SELECT 1 
        FROM docketwatch.dbo.case_celebrity_matches m
        WHERE m.fk_case = c.id 
          AND m.fk_celebrity = ce.id
    );
</cfquery>

<cfquery datasource="Reach" name="updReview" result="updReviewResult">
    UPDATE [docketwatch].[dbo].[cases]
    SET [status] = 'Review'
    WHERE [status] = 'New';
</cfquery>

<cfquery datasource="Reach" name="updRemoved" result="updRemovedResult">
    UPDATE [docketwatch].[dbo].[cases]
    SET [status] = 'Removed'
    WHERE [status] = 'Deleted';
</cfquery>

<cfset stats = {
    "status": "completed",
    "insertedCelebrityMatches": insResult.recordCount,
    "casesUpdatedToReview": updReviewResult.recordCount,
    "casesUpdatedToRemoved": updRemovedResult.recordCount
}>

<cfoutput>#serializeJSON(stats)#</cfoutput>
