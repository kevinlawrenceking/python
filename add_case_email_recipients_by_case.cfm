<Cfparam name="case_id" default="0" />


<!--- coldfusion comments --->
<!--- Get all cases with their fk_tool --->
<cfquery name="getCases" datasource="reach">
    SELECT id AS case_id, fk_tool
    FROM docketwatch.dbo.cases where [status] = 'Tracked'
    and id = <cfqueryparam value="#case_id#" cfsqltype="cf_sql_integer">
</cfquery>

<!--- coldfusion comments --->
<!--- Get all tool owners --->
<cfquery name="getToolOwners" datasource="reach">
    SELECT fk_tool, fk_user
    FROM docketwatch.dbo.toolOwners
</cfquery>

<!--- coldfusion comments --->
<!--- For each case, get owners for that tool and add to case_email_recipients if missing --->
<cfloop query="getCases">
    <cfset thisCaseId = getCases.case_id>
    <cfset thisToolId = getCases.fk_tool>

    <cfloop query="getToolOwners">
        <cfif getToolOwners.fk_tool EQ thisToolId>
            <!--- coldfusion comments --->
            <!--- Check if this case/user is already a recipient --->
            <cfquery name="checkRecipient" datasource="reach">
                SELECT COUNT(*) AS cnt
                FROM docketwatch.dbo.case_email_recipients
                WHERE fk_case = <cfqueryparam value="#thisCaseId#" cfsqltype="cf_sql_integer">
                  AND fk_username = <cfqueryparam value="#getToolOwners.fk_user#" cfsqltype="cf_sql_varchar" maxlength="100">
            </cfquery>

            <cfif checkRecipient.cnt EQ 0>
                <!--- coldfusion comments --->
                <!--- Insert as recipient --->
                <cfquery datasource="reach">
                    INSERT INTO docketwatch.dbo.case_email_recipients
                        (fk_case, notify, added_on, fk_username)
                    VALUES (
                        <cfqueryparam value="#thisCaseId#" cfsqltype="cf_sql_integer">,
                        <cfqueryparam value="1" cfsqltype="cf_sql_bit">,
                        <cfqueryparam value="#now()#" cfsqltype="cf_sql_timestamp">,
                        <cfqueryparam value="#getToolOwners.fk_user#" cfsqltype="cf_sql_varchar" maxlength="100">
                    )
                </cfquery>
            </cfif>
        </cfif>
    </cfloop>
</cfloop>
