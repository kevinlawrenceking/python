<cfset currentuser = getAuthUser()   />
  
    <cfquery name="x" datasource="reach">
SELECT tp.id, tp.fk_priority, tp.case_name, tp.case_url
FROM docketwatch.dbo.temp_priority tp
LEFT JOIN docketwatch.dbo.cases c
    ON RTRIM(LTRIM(tp.case_url)) = RTRIM(LTRIM(c.case_url))
WHERE c.case_url IS NULL order by case_name
    </cfquery>


    <Cfloop query="x">


<Cfset new_caseurl = x.case_url />
<Cfset new_caseNumber = "Unknown" />
<Cfset new_casename = x.case_name />
<Cfset currentuser = "xkking" />
<cfset tool = 2 />


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

    </cfloop>
  
  