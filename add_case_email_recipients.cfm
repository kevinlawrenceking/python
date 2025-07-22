<Cfparam name="case_id" default="0" />


<!--- coldfusion comments --->
<!--- Get all cases with their fk_tool --->
<cfquery name="getCases" datasource="reach">
    SELECT c.id AS case_id, t.fk_user
    FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.toolOwners t on t.fk_tool = c.fk_tool
where c.[status] = 'Tracked'  

</cfquery>

<cfloop query="getCases">
    <cfset thisCaseId = getCases.case_id>
    <cfset fk_user = getCases.fk_user>
 
            <cfquery name="checkRecipient" datasource="reach">
                SELECT COUNT(*) AS cnt
                FROM docketwatch.dbo.case_email_recipients
                WHERE fk_case = <cfqueryparam value="#thisCaseId#" cfsqltype="cf_sql_integer">
                  AND fk_username = <cfqueryparam value="#fk_user#" cfsqltype="cf_sql_varchar" maxlength="100">
            </cfquery>

            <cfif checkRecipient.cnt EQ 0>
      
                <cfquery datasource="reach">
                    INSERT INTO docketwatch.dbo.case_email_recipients
                        (fk_case, notify, added_on, fk_username)
                    VALUES (
                        <cfqueryparam value="#thisCaseId#" cfsqltype="cf_sql_integer">,
                        <cfqueryparam value="1" cfsqltype="cf_sql_bit">,
                        <cfqueryparam value="#now()#" cfsqltype="cf_sql_timestamp">,
                        <cfqueryparam value="#fk_user#" cfsqltype="cf_sql_varchar" maxlength="100">
                    )
                </cfquery>
            </cfif>

 
 
    </cfloop>
 
