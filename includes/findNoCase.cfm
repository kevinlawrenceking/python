<cffunction name="fncFindNoCase" returntype="boolean">
    <cfargument name="content" type="string" required="true">

    <cfif find("No match found for case number", arguments.content) GT 0>
        <cfreturn true>
    <cfelse>
        <cfreturn false>
    </cfif>
</cffunction>
