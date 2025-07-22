<cfparam name="form.id" type="numeric" />
<cfparam name="form.case_number" default="" />
<cfparam name="form.case_name" default="" />
<cfparam name="form.status" default="Tracked" />
<cfparam name="form.fk_court" default="UNK" />
<cfparam name="form.case_type" default="" />
<cfparam name="form.case_url" default="" />
<cfparam name="form.fk_tool" default="" />
<cfparam name="form.fk_priority" default="2" />
<cfparam name="form.update_external" default="0">
<cfset isExternalUpdate = form.update_external EQ "on">

<!--- Update master case --->
<cfquery datasource="reach">
    UPDATE [docketwatch].[dbo].[cases]
       SET
           [case_number] = <cfqueryparam value="#form.case_number#" cfsqltype="cf_sql_varchar" maxlength="100">,
           [case_name] = <cfqueryparam value="#form.case_name#" cfsqltype="cf_sql_varchar" maxlength="500">,
           [status] = <cfqueryparam value="#form.status#" cfsqltype="cf_sql_varchar" maxlength="50">,
           [fk_court] = <cfqueryparam value="#form.fk_court#" cfsqltype="cf_sql_varchar" maxlength="5">,
           [case_type] = <cfqueryparam value="#form.case_type#" cfsqltype="cf_sql_varchar" maxlength="200">,
           [case_url] = <cfqueryparam value="#form.case_url#" cfsqltype="cf_sql_varchar" maxlength="255">,
           [fk_tool] = <cfqueryparam value="#form.fk_tool#" cfsqltype="cf_sql_integer">,
           [fk_priority] = <cfqueryparam value="#form.fk_priority#" cfsqltype="cf_sql_integer">
     WHERE id = <cfqueryparam value="#form.id#" cfsqltype="cf_sql_integer">
</cfquery>


<cfquery datasource="reach">
DELETE from [docketwatch].[dbo].[case_email_recipients]
where fk_case = <cfqueryparam value="#form.id#" cfsqltype="cf_sql_integer"> and notify = 1
</cfquery>

<cfset case_id = form.id />

 <cfinclude template="add_case_email_recipients_by_case.cfm" />

<cfif form.update_external eq "on">
 external is on!<BR>
    <cfif #form.fk_tool# eq 2>
tool is 2<BR>
        <cfinclude template="pacer_single.cfm">

    </cfif>

</cfif>
 
<!--- Redirect to case details page --->
<cflocation url="case_details.cfm?id=#form.id#" addtoken="no">
