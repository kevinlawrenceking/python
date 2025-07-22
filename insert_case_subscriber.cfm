<cfcontent type="application/json">
<cftry>
    <!--- Read JSON body --->
    <cfset data = deserializeJson(toString(getHttpRequestData().content))>

    <!--- Validate inputs --->
    <cfif not structKeyExists(data, "fk_case") or not structKeyExists(data, "fk_username")>
        <cfoutput>#serializeJson({ success=false, message="Missing required parameters." })#</cfoutput>
        <cfabort>
    </cfif>

    <!--- Insert if not already present --->
<!--- First check if the record already exists --->
<cfquery name="checkExists" datasource="Reach">
    SELECT id FROM docketwatch.dbo.case_email_recipients
    WHERE fk_case = <cfqueryparam value="#data.fk_case#" cfsqltype="cf_sql_integer">
      AND fk_username = <cfqueryparam value="#data.fk_username#" cfsqltype="cf_sql_varchar">
</cfquery>

<cfif checkExists.recordcount EQ 0>
    <!--- Perform the insert and get the identity value --->
    <cfquery name="insertSubscriber" datasource="Reach">
        INSERT INTO docketwatch.dbo.case_email_recipients (fk_case, fk_username)
        VALUES (
            <cfqueryparam value="#data.fk_case#" cfsqltype="cf_sql_integer">,
            <cfqueryparam value="#data.fk_username#" cfsqltype="cf_sql_varchar">
        );
        SELECT CAST(SCOPE_IDENTITY() AS INT) AS new_id;
    </cfquery>
    <cfset newId = insertSubscriber.new_id>
<cfelse>
    <cfset newId = checkExists.id>
</cfif>


<!--- After INSERT, fetch user info for display --->
<cfquery name="userInfo" datasource="Reach">
    SELECT firstname, lastname, email, userRole
    FROM docketwatch.dbo.users
    WHERE username = <cfqueryparam value="#data.fk_username#" cfsqltype="cf_sql_varchar">
</cfquery>


<cfset response = {
    success = true,
    id = newId,
    firstname = userInfo.firstname,
    lastname = userInfo.lastname,
    email = userInfo.email,
    userRole = userInfo.userRole
}>

<cfoutput>#serializeJson(response)#</cfoutput>


<cfcatch>
    <cfoutput>#serializeJson({ success=false, message=cfcatch.message })#</cfoutput>
</cfcatch>
</cftry>
