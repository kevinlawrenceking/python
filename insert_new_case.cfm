<cfsetting showdebugoutput="false">

<cftry>

    <cfset requestData = DeserializeJSON(ToString(GetHttpRequestData().content))>

    <cfif NOT structKeyExists(requestData, "caseNumber")>
  <cfset requestData.caseNumber = "">
</cfif>

<cfif NOT structKeyExists(requestData, "caseName")>
  <cfset requestData.caseName = "">
</cfif>

<cfif NOT structKeyExists(requestData, "caseUrl")>
  <cfset requestData.caseUrl = "">
</cfif>


    <cfif len(trim(requestData.caseName)) eq 0>
        <cfset new_casename = "Unknown" />
    <cfelse>
        <cfset new_casename = requestData.caseName />
    </cfif>

        <cfif len(trim(requestData.caseNumber)) eq 0>
        <cfset new_casenumber = "Unknown" />
    <cfelse>
        <cfset new_caseNumber = requestData.caseNumber />
    </cfif>

    <cfif len(trim(requestData.caseUrl)) eq 0>
        <cfset new_caseUrl = "Unknown" />
    <cfelse>
        <cfset new_caseUrl = requestData.caseUrl />
    </cfif>


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
        <cfqueryparam value="#requestData.currentuser#" cfsqltype="cf_sql_varchar">,
        GETDATE(),
        GETDATE()
      )
    </cfquery>

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
        <cfqueryparam value="#requestData.caseUrl#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#caseInsert.generatedkey#" cfsqltype="cf_sql_integer">,
        <cfqueryparam value="#requestData.tool#" cfsqltype="cf_sql_integer">,
        <cfqueryparam value="#new_caseNumber#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#new_casename#" cfsqltype="cf_sql_varchar">,
        
        GETDATE(),
        1,
        <cfqueryparam value="#requestData.caseNumber#" cfsqltype="cf_sql_varchar">
      )
    </cfquery>

    <cfif requestData.tool EQ 2>

  <!--- Run PACER Single Scraper for New Case --->
<cfset bat_path = "u:\TMZTOOLS\python\docketwatch_pacer_scraper_single.bat">
<cfexecute name="#bat_path#"
           arguments="#caseInsert.generatedkey#"
           timeout="9999"
           variable="output"
           errorVariable="errorOutput">
</cfexecute>
</cfif>

<cfif requestData.tool EQ 13>

  <!--- Run Broward Scraper with Case ID Parameter --->
  <cfset bat_path = "u:\TMZTOOLS\python\docketwatch_broward_scraper_single.bat">
  <cfexecute name="#bat_path#"
             arguments="#caseInsert.generatedkey#"
             timeout="9999"
             variable="output"
             errorVariable="errorOutput">
  </cfexecute>

</cfif>

    <cfif requestData.tool EQ 25>

  <!--- Run Orange County, FL Single Scraper for New Case --->
<cfset bat_path = "u:\TMZTOOLS\python\docketwatch_orange_FL_scraper_single.bat">
<cfexecute name="#bat_path#"
           arguments="#caseInsert.generatedkey#"
           timeout="9999"
           variable="output"
           errorVariable="errorOutput">
</cfexecute>
</cfif>

<cfcontent type="application/json">
<cfoutput>#SerializeJSON({success=true, inserted_case_id=caseInsert.generatedkey})#</cfoutput>

<cfcatch>
  <cfoutput>
      #SerializeJSON({
        success:false,
        message:cfcatch.message,
        detail:cfcatch.detail,
        sql: (StructKeyExists(cfcatch,"sql") ? cfcatch.sql : "")
      })#
    </cfoutput>
</cfcatch>

</cftry>
