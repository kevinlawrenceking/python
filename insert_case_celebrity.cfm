
<cftry>
    <cfset caseId = form.fk_case>
    <cfset celebrityId = form.fk_celebrity>
    <cfset username = form.fk_user ?: "unknown">

    <cfquery name="check" datasource="Reach">
        SELECT COUNT(*) AS existsCount
        FROM docketwatch.dbo.case_celebrity_matches
        WHERE fk_case = <cfqueryparam value="#caseId#" cfsqltype="cf_sql_integer">
          AND fk_celebrity = <cfqueryparam value="#celebrityId#" cfsqltype="cf_sql_varchar">
    </cfquery>

    <cfif check.existsCount EQ 0>
        <cfquery datasource="Reach" result="cmInsert">
            INSERT INTO docketwatch.dbo.case_celebrity_matches (
                fk_case, match_status, created_at, updated_at, fk_celebrity, created_by
            ) VALUES (
                <cfqueryparam value="#caseId#" cfsqltype="cf_sql_integer">,
                'Tracked',
                GETDATE(), GETDATE(),
                <cfqueryparam value="#celebrityId#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#username#" cfsqltype="cf_sql_varchar">
            )
        </cfquery>
        <cfset inserted_id = cmInsert.generatedkey >
        <Cfelse>
         <cfset inserted_id = "">
    </cfif>

    <cfquery name="details" datasource="Reach">
        SELECT 
            c.name AS celebrity_name,
            (SELECT TOP 1 name FROM docketwatch.dbo.celebrity_names 
             WHERE fk_celebrity = c.id AND type = 'Legal' AND isDeleted = 0) AS legal_name,
            0.00 AS probability_score, 0.00 AS priority_score, 0.00 AS ranking_score
        FROM docketwatch.dbo.celebrities c
        WHERE c.id = <cfqueryparam value="#celebrityId#" cfsqltype="cf_sql_varchar">
    </cfquery>
<cfcontent type="application/json">
    <cfoutput>
        #serializeJSON({
            status = "success",
            match_status = "Tracked",
            celebrity_id = celebrityId,
            celebrity_name = details.celebrity_name,
            legal_name = details.legal_name,
            probability_score = details.probability_score,
            priority_score = details.priority_score,
            ranking_score = details.ranking_score,
            match_id = inserted_id
        })#
    </cfoutput>

<cfcatch>
<cfset errorDetail = {
    status = "error",
    error = cfcatch.message,
    detail = cfcatch.detail ?: "",
    sql = cfcatch.sql ?: "",
    where = cfcatch.where ?: ""
}>
<cfoutput>#serializeJSON(errorDetail)#</cfoutput>
</cfcatch>
 
</cftry>
