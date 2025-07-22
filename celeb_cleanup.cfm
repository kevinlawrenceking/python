<h2>Celebrity Cleanup Log</h2>
 

<cfquery name="qDupAliasNames" datasource="Reach">
SELECT a.name
FROM docketwatch.dbo.celebrity_names a
JOIN docketwatch.dbo.celebrities c ON c.id = a.fk_celebrity
WHERE a.isDeleted = 0 AND c.isDeleted = 0
GROUP BY a.name
HAVING COUNT(DISTINCT a.fk_celebrity) > 1

</cfquery>

<cfloop query="qDupAliasNames">
    <cfset aliasName = qDupAliasNames.name>

    <!--- Get all celebrities sharing this alias --->
    <cfquery name="qRelatedCelebs" datasource="Reach">
        SELECT 
            c.id AS celebrity_id,
            c.name AS celebrity_name,
            c.appearances
        FROM docketwatch.dbo.celebrity_names a
        JOIN docketwatch.dbo.celebrities c ON c.id = a.fk_celebrity
        WHERE a.name = <cfqueryparam value="#aliasName#" cfsqltype="cf_sql_varchar">
          AND a.isDeleted = 0
          AND c.isDeleted = 0
    </cfquery>

    <!--- Determine which celebrity to keep --->
    <cfset keepId = "">
    <cfset keepName = "">
    <cfset maxAppearances = -1>

    <cfloop query="qRelatedCelebs">
        <cfif qRelatedCelebs.appearances GT maxAppearances>
            <cfset maxAppearances = qRelatedCelebs.appearances>
            <cfset keepId = qRelatedCelebs.celebrity_id>
            <cfset keepName = qRelatedCelebs.celebrity_name>
        </cfif>
    </cfloop>

    <cfoutput>
    <p>
    <strong>Alias:</strong> #aliasName#<br>
    <strong>Kept:</strong> #keepName# (#maxAppearances# appearances)<br>
    <strong>Merged:</strong><br>
    </p>
    <ul>
    </cfoutput>

    <!--- Delete all other celebrities and their aliases --->
    <cfloop query="qRelatedCelebs">
        <cfif qRelatedCelebs.celebrity_id NEQ keepId>
            <!--- Soft-delete the duplicate celebrity --->
            <cfquery datasource="Reach">
                UPDATE docketwatch.dbo.celebrities
                SET isDeleted = 1,
                    correct_id = <cfqueryparam value="#keepId#" cfsqltype="cf_sql_varchar">
                WHERE id = <cfqueryparam value="#qRelatedCelebs.celebrity_id#" cfsqltype="cf_sql_varchar">
            </cfquery>

            <!--- Soft-delete all celebrity_names for the deleted celebrity --->
            <cfquery datasource="Reach">
                UPDATE docketwatch.dbo.celebrity_names
                SET isDeleted = 1
                WHERE fk_celebrity = <cfqueryparam value="#qRelatedCelebs.celebrity_id#" cfsqltype="cf_sql_varchar">
            </cfquery>

            <cfoutput>
                <li>#qRelatedCelebs.celebrity_name# (#qRelatedCelebs.appearances# appearances)</li>
            </cfoutput>
        </cfif>
    </cfloop>

    <cfoutput></ul><hr></cfoutput>
</cfloop>
