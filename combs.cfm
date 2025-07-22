
<!--- Step 1: Find tracked cases with no linked celebrities and 'combs' in the name --->

<Cfset shaunCombsId = "0B125FC5-B236-4033-AC1A-8CFD3CE2931B" />
<cfquery name="qMissingCombsCases" datasource="Reach">
SELECT c.id
FROM docketwatch.dbo.cases c
LEFT JOIN docketwatch.dbo.case_celebrity_matches cm 
  ON cm.fk_case = c.id AND cm.match_status <> 'Removed'
WHERE c.status = 'Tracked'
  AND cm.id IS NULL
  AND c.case_name LIKE '%combs%'
</cfquery>

<!--- Step 2: Insert missing match entries --->
<cfloop query="qMissingCombsCases">
    <cfquery datasource="Reach">
    INSERT INTO docketwatch.dbo.case_celebrity_matches (
        fk_case, fk_celebrity, match_status, created_at, updated_at, created_by
    )
    VALUES (
        <cfqueryparam value="#qMissingCombsCases.id#" cfsqltype="cf_sql_varchar">,
        <cfqueryparam value="#shaunCombsId#" cfsqltype="cf_sql_varchar">,
        'Verified',
        GETDATE(), GETDATE(),
        <cfqueryparam value="#getAuthUser()#" cfsqltype="cf_sql_varchar">
    )
    </cfquery>
</cfloop>
