<cfcontent type="application/json">

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

<cfoutput>{"status": "completed"}</cfoutput>
