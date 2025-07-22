<cfcontent type="application/json" />

<cfquery name="getCaseMatches" datasource="reach">
    SELECT 
        cm.id,
        c.case_number, 
        c.case_name, 
        ce.name AS celebrity_name, 
        c.status,
        cm.probability_score, 
        cm.priority_score, 
        cm.ranking_score,
        cm.fk_celebrity,
        cm.match_status,
        CONVERT(VARCHAR, cm.created_at, 126) AS sortable_created_at,
        FORMAT(cm.created_at, 'MM-dd-yy hh:mm tt') AS formatted_created_at,
        'case_details.cfm?id=' + CAST(c.id AS VARCHAR) AS internal_case_url,
        c.case_url AS external_case_url
    FROM docketwatch.dbo.case_celebrity_matches cm
    JOIN docketwatch.dbo.cases c ON cm.fk_case = c.id
    JOIN docketwatch.dbo.celebrities ce ON ce.id = cm.fk_celebrity
    WHERE cm.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
    and cm.match_status <> <cfqueryparam value="Verified" cfsqltype="cf_sql_varchar">
    and c.status <> 'Tracked'
    and c.status <> 'Removed'
    and c.status <> 'Closed'
    and ce.isdeleted <> 1
    ORDER BY cm.ranking_score DESC, cm.priority_score DESC
</cfquery>
<cfset result = []>

<cfloop query="getCaseMatches">
    <cfset badgeType = "weak"> 

    <cfif ranking_score GTE 9>
        <cfset badgeType = "hot">
    <cfelseif ranking_score GTE 7>
        <cfset badgeType = "strong">
    <cfelseif ranking_score GTE 4>
        <cfset badgeType = "possible">
    </cfif>


    <cfset arrayAppend(result, {
        id: id,
        case_number: case_number,
        case_name: case_name,
        celebrity_name: celebrity_name,
        fk_celebrity: fk_celebrity,
        ranking_score: ranking_score,
        ranking_badge: (
            ranking_score GTE 9 ? "hot" :
            ranking_score GTE 7 ? "strong" :
            ranking_score GTE 4 ? "possible" :
            "weak"
        ),
        sortable_created_at: sortable_created_at,
        formatted_created_at: formatted_created_at,
        match_status: match_status,
        internal_case_url: internal_case_url,
        external_case_url: external_case_url,
        case_status: status
    })>
</cfloop>


<cfoutput>#serializeJSON(result)#</cfoutput>

