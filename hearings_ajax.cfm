<cfparam name="url.case_id" default="">

<!--- Query to Fetch Hearings for the Given Case --->
<cfquery name="getHearings" datasource="reach">
    SELECT 
         h.[ID],
         h.[hearing_type] AS type,
         h.[hearing_datetime] AS date_time,
         h.[case_utype_description] AS category,
         c.court_name AS courthouse,
         h.[court_session_description] AS department
    FROM docketwatch.dbo.hearings h
    LEFT JOIN docketwatch.dbo.departments d ON d.ID = h.fk_department
    LEFT JOIN docketwatch.dbo.courts c ON c.court_id = h.fk_court_id
    WHERE h.fk_case = <cfqueryparam value="#url.case_id#" cfsqltype="cf_sql_varchar">
</cfquery>

<!--- Convert Query to JSON Format for DataTables --->
<cfset data = []>
<cfloop query="getHearings">
    <cfset row = {
        "ID"         : getHearings.ID,
        "type"       : getHearings.type,
        "date_time"  : getHearings.date_time,
        "category"   : getHearings.category,
        "courthouse" : getHearings.courthouse,
        "department" : getHearings.department
    }>
    <cfset arrayAppend(data, row)>
</cfloop>

<!--- Output JSON Response in Correct Format --->
<cfcontent type="application/json" reset="true">
<cfoutput>#serializeJSON(data)#</cfoutput>
