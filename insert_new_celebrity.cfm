<cfcontent type="application/json" />
<cftry>
    <cfset newName = trim(form.name ?: "")>

    <cfif newName EQ "">
        <cfoutput>#serializeJSON({error = "Name is required."})#</cfoutput>
        <cfabort>
    </cfif>

    <cfset createdBy = getAuthUser()>
    <cfset celebrityID = createUUID()>
    <cfset nameID = createUUID()>

    <!--- Insert new celebrity --->
    <cfquery datasource="Reach">
        INSERT INTO docketwatch.dbo.celebrities (
            id, name, verified, isDeleted, created_by, created_at
        ) VALUES (
            <cfqueryparam value="#celebrityID#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#newName#" cfsqltype="cf_sql_varchar">,
            0, 0,
            <cfqueryparam value="#createdBy#" cfsqltype="cf_sql_varchar">,
            GETDATE()
        )
    </cfquery>

    <!--- Insert primary name --->
    <cfquery datasource="Reach">
        INSERT INTO docketwatch.dbo.celebrity_names (
            id, fk_celebrity, name, type, isPrimary, isDeleted, created_by, created_at
        ) VALUES (
            <cfqueryparam value="#nameID#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#celebrityID#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#newName#" cfsqltype="cf_sql_varchar">,
            'Alias',
            1, 0,
            <cfqueryparam value="#createdBy#" cfsqltype="cf_sql_varchar">,
            GETDATE()
        )
    </cfquery>

    <cfoutput>
        #serializeJSON({
            celebrity_id = celebrityID,
            name = newName,
            status = "added"
        })#
    </cfoutput>

<cfcatch>
    <cfoutput>#serializeJSON({error = cfcatch.message})#</cfoutput>
</cfcatch>
</cftry>
