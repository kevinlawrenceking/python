<cfparam name="fk_tool" type="numeric" default="2" />
<cfparam name="fk_court" type="any" default="UNK">
<cfparam name="status" default="Tracked" />

<!--- 1. Insert blank case --->
<cfquery name="insertCase" datasource="reach">
    INSERT INTO docketwatch.dbo.cases
    (
        case_number,
        case_name,
        status,
        fk_court,
        fk_tool
    )
    VALUES
    (
        NULL,
        NULL,
        <cfqueryparam value="#status#" cfsqltype="cf_sql_varchar" maxlength="50">,
        <cfqueryparam value="#fk_court#" cfsqltype="cf_sql_varchar" maxlength="5" null="#fk_court EQ ''#">,
        <cfqueryparam value="#fk_tool#" cfsqltype="cf_sql_integer">
    );
    SELECT SCOPE_IDENTITY() AS new_case_id;
</cfquery>


<cfset new_case_id = insertCase.new_case_id>
<!--- 2. Insert blank tool_cases row 

<cfquery datasource="reach">
    INSERT INTO docketwatch.dbo.tool_cases
    (
        fk_case,
        fk_tool,
        tool_case_number,
        tool_case_name,
        case_url,
        last_updated
    )
    VALUES
    (
        <cfqueryparam value="#new_case_id#" cfsqltype="cf_sql_integer">,
        <cfqueryparam value="#fk_tool#" cfsqltype="cf_sql_integer">,
        NULL, NULL, NULL, GETDATE()
    )
</cfquery>
--->
<!--- 3. Redirect to the update form --->
<cflocation url="case_update.cfm?id=#new_case_id#&case_mode=new" addtoken="no">
