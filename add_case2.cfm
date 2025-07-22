<cfset currentuser = getAuthUser()   />
  
  <cfquery datasource="Reach" result="caseInsert">
      INSERT INTO docketwatch.dbo.cases (
        case_url,
        case_number, 
        case_name, 
        status, 
        owner, 
        created_at, 
        last_updated
      ) VALUES (
        <cfqueryparam value="#new_caseUrl#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#new_casename#" cfsqltype="cf_sql_varchar">,
        'Tracked',
        <cfqueryparam value="#currentuser#" cfsqltype="cf_sql_varchar">,
        GETDATE(),
        GETDATE()
      )
    </cfquery>
<!---
    <cfquery datasource="Reach">
      INSERT INTO docketwatch.dbo.tool_cases (
        case_url,
        fk_case, 
        fk_tool, 
        tool_case_number, 
        tool_case_name, 
        last_updated, 
        is_tracked,
        tool_case_id
      ) VALUES (
        <cfqueryparam value="#new_caseUrl#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#caseInsert.generatedkey#" cfsqltype="cf_sql_integer">,
        <cfqueryparam value="#tool#" cfsqltype="cf_sql_integer">,
        <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#new_casename#" cfsqltype="cf_sql_varchar">,
        
        GETDATE(),
        1,
        <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">
      )
    </cfquery> --->

    <Cfset case_id = caseinsert.generatedkey />

    <cfinclude template="add_case_email_recipients_by_case.cfm" />
    
<cflocation url="case_details.cfm?id=#caseinsert.generatedkey#" addtoken="no" />