 
<cfquery name="getTools" datasource="reach">
    SELECT id, owners
    FROM docketwatch.dbo.tools
</cfquery>

<cfloop query="getTools">
    <!--- coldfusion comments --->
    <!--- Parse owners JSON array for each tool --->
    <cfset ownersArray = deserializeJson(getTools.owners)>

    <cfloop array="#ownersArray#" index="ownerUsername">
        <!--- coldfusion comments --->
        <!--- Check if this tool/user pair already exists --->
        <cfquery name="checkExist" datasource="reach">
            SELECT COUNT(*) AS cnt
            FROM docketwatch.dbo.toolOwners
            WHERE fk_tool = <cfqueryparam value="#getTools.id#" cfsqltype="cf_sql_integer">
              AND fk_user = <cfqueryparam value="#ownerUsername#" cfsqltype="cf_sql_varchar" maxlength="100">
        </cfquery>

        <cfif checkExist.cnt EQ 0>
            <!--- coldfusion comments --->
            <!--- Insert new xref row --->
            <cfquery datasource="reach">
                INSERT INTO docketwatch.dbo.toolOwners (fk_tool, fk_user)
                VALUES (
                    <cfqueryparam value="#getTools.id#" cfsqltype="cf_sql_integer">,
                    <cfqueryparam value="#ownerUsername#" cfsqltype="cf_sql_varchar" maxlength="100">
                )
            </cfquery>
        </cfif>
    </cfloop>
</cfloop>
