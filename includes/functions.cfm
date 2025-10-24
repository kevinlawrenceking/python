<!--- Normalize Case Name: Remove Extra Words, Reformat Names --->
<cffunction name="fncNormalizeCaseName" returntype="string">
    <cfargument name="caseName" type="string" required="yes">

    <cfset var cleanName = caseName>

    <!--- Remove known phrases --->
    <cfset cleanName = rereplace(cleanName, " - (CONSERVATORSHIP|DECEDENT|GUARDIANSHIP|MINOR'S COMPROMISE|IN THE MATTER OF|DATED.*)", "", "all")>

    <!--- Remove multiple spaces --->
    <cfset cleanName = rereplace(cleanName, "\s+", " ", "all")>

    <!--- Reformat "LAST, FIRST" to "FIRST LAST" --->
    <cfset cleanName = listlast(cleanName, ",") & " " & listfirst(cleanName, ",")>

    <!--- Convert to uppercase for comparison --->
    <cfset cleanName = ucase(trim(cleanName))>

    <cfreturn cleanName>
</cffunction>

<!--- Check if Celebrity Name Matches Case Name --->
<cffunction name="fncIsMatch" returntype="boolean">
    <cfargument name="caseName" type="string" required="yes">
    <cfargument name="celebName" type="string" required="yes">

    <cfset var caseWords = listToArray(caseName, " ")>
    <cfset var celebWords = listToArray(ucase(celebName), " ")>
    <cfset var match = true>

    <!--- Check if all words in celebName exist in caseName --->
    <cfloop array="#celebWords#" index="word">
        <cfif not arrayFind(caseWords, word)>
            <cfset match = false>
            <cfbreak>
        </cfif>
    </cfloop>

    <cfreturn match>
</cffunction>
