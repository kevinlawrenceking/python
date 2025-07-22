<cfquery datasource="Reach" name="cases">
    SELECT [id], [tool_case_name] AS new_casename, [case_url] AS new_case_url
    FROM [docketwatch].[dbo].[cases_to_find]
    WHERE status = 'Pending' AND tool_case_id IS NULL
</cfquery>

<cfloop query="cases">

    <cfset new_casenumber = "Unknown" />
    <cfset new_casename = cases.new_casename />
    <cfset new_tool_case_url = cases.new_case_url />
    <cfset new_id = cases.id />

    <!--- Insert into cases --->
    <cfquery datasource="Reach" result="caseInsert">
        INSERT INTO docketwatch.dbo.cases (
            case_number, 
            case_name, 
            status, 
            owner, 
            created_at, 
            last_updated
        ) VALUES (
            <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#new_casename#" cfsqltype="cf_sql_varchar">,
            'Tracked',
            <cfqueryparam value="System" cfsqltype="cf_sql_varchar">,
            GETDATE(),
            GETDATE()
        )
    </cfquery>

    <!--- Insert into tool_cases --->
    <cfquery datasource="Reach" result="toolCaseInsert">
        INSERT INTO docketwatch.dbo.tool_cases (
            fk_case, 
            fk_tool, 
            case_url,
            tool_case_number, 
            tool_case_name, 
            last_updated, 
            is_tracked,
            tool_case_id
        ) VALUES (
            <cfqueryparam value="#caseInsert.generatedkey#" cfsqltype="cf_sql_integer">,
            <cfqueryparam value="2" cfsqltype="cf_sql_integer">,
            <cfqueryparam value="#new_tool_case_url#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#new_casename#" cfsqltype="cf_sql_varchar">,
            GETDATE(),
            1,
            <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">
        )
    </cfquery>

    <!--- Update the case_url in cases table --->
    <cfset new_case_url = "case_details.cfm?id=" & caseInsert.generatedkey />

    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases
        SET case_url = <cfqueryparam value="#new_case_url#" cfsqltype="cf_sql_varchar">
        WHERE id = <cfqueryparam value="#caseInsert.generatedkey#" cfsqltype="cf_sql_integer">
    </cfquery>

    <!--- Update cases_to_find with status and tool_case_id --->
    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.cases_to_find
        SET status = <cfqueryparam value="Found" cfsqltype="cf_sql_varchar">,
            tool_case_id = <cfqueryparam value="#toolCaseInsert.generatedkey#" cfsqltype="cf_sql_integer">
        WHERE id = <cfqueryparam value="#new_id#" cfsqltype="cf_sql_integer">
    </cfquery>

</cfloop>
