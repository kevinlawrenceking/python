<cfsetting showdebugoutput="false">

<cftry>

    <cfset requestData = DeserializeJSON(ToString(GetHttpRequestData().content))>

    <cfif NOT structKeyExists(requestData, "case_id")>
<Cfabort>
<Cfelse>
<Cfset case_id = request_data.case_id >
</cfif>


    <cfif requestData.tool EQ 2>

  <!--- Run PACER Single Scraper for New Case --->
<cfset bat_path = "u:\TMZTOOLS\python\docketwatch_pacer_scraper_single.bat">
<cfexecute name="#bat_path#"
           arguments="#case_id#"
           timeout="9999"
           variable="output"
           errorVariable="errorOutput">
</cfexecute>
</cfif>

<cfif requestData.tool EQ 13>

  <!--- Run Broward Scraper with Case ID Parameter --->
  <cfset bat_path = "u:\TMZTOOLS\python\docketwatch_broward_scraper_single.bat">
  <cfexecute name="#bat_path#"
             arguments="#case_id#"
             timeout="9999"
             variable="output"
             errorVariable="errorOutput">
  </cfexecute>

</cfif>

    <cfif requestData.tool EQ 25>

  <!--- Run Orange County, FL Single Scraper for New Case --->
<cfset bat_path = "u:\TMZTOOLS\python\docketwatch_orange_FL_scraper_single.bat">
<cfexecute name="#bat_path#"
           arguments="#case_id#"
           timeout="9999"
           variable="output"
           errorVariable="errorOutput">
</cfexecute>
</cfif>

<cfcontent type="application/json">
<cfoutput>#SerializeJSON({success=true, updated_case_id=case_id})#</cfoutput>

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
