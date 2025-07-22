<html>
<head>
    <title>Case Name Cleaner Testing Form</title>
    <!--- Bootstrap CSS --->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
    <div class="container mt-5">
        <h1>Case Name Cleaner Testing Form</h1>
        
        <!--- Ensure form variables exist --->
        <cfparam name="form.caseName" default="">
        <cfparam name="form.county" default="">
        
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

            <cfif arguments.code eq "LAC">
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\s(VS\.?|AND)\s", "|", "all")>
<cfelseif arguments.code eq "NYC">
    <cfset cleanedName = rereplaceNoCase(cleanedName, "\sv\.?\s", "|", "all")>
</cfif>
            
            <cfreturn trim(cleanedName)>
        </cffunction>
        
        <!--- Process form submission --->
        <cfif structKeyExists(form, "submit")>
            <cfset cleanedResult = cleanCaseName(form.caseName, form.county)>
            <!--- Split the Case Name into Individual Parties --->
            <cfset parties = listToArray(cleanedResult, "|")>
            <cfoutput>
                <div class="alert alert-info" role="alert">
                    <strong>Cleaned Case Name:</strong> #cleanedResult#
                </div>
                <div class="mt-3">
                    <h3>Parties</h3>
                    <cfloop from="1" to="#arrayLen(parties)#" index="i">
                        <p><strong>Party #i#:</strong> #trim(parties[i])#</p>
                    </cfloop>
                </div>
            </cfoutput>
        </cfif>
        
        <!--- Testing form --->
        <form method="post" action="" class="mt-4">
            <div class="form-group">
                <label for="caseName">Case Name:</label>
                <input type="text" name="caseName" id="caseName" class="form-control" value="<cfoutput>#form.caseName#</cfoutput>">
            </div>
            <div class="form-group">
                <label for="county">County:</label>
                <select name="county" id="county" class="form-control">
                    <option value="LAC" <cfif form.county eq "LAC">selected</cfif>>Los Angeles (LAC)</option>
                    <option value="NYC" <cfif form.county eq "NYC">selected</cfif>>New York (NYC)</option>
                </select>
            </div>
            <button type="submit" name="submit" class="btn btn-primary">Submit</button>
        </form>
    </div>
    
    <!--- Bootstrap JS, Popper.js, and jQuery --->
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.1/dist/umd/popper.min.js"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
