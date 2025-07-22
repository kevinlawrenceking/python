<cfcontent type="application/json; charset=utf-8">

<cfquery name="qCelebs" datasource="reach">
   SELECT
        c.id AS celeb_id,
        c.name AS celebrity_name,
        ISNULL(c.priority_score, 0) AS priority_score,
        ISNULL(c.relevancy_index, 0) AS relevancy_index,
        ISNULL(c.verified, 0) AS verified,
        e.external_id AS wiki_id,
        COUNT(cm.id) AS case_count,
        (
            SELECT 
                STUFF((
                    SELECT ' ' + cn.name
                    FROM docketwatch.dbo.celebrity_names cn
                    WHERE cn.fk_celebrity = c.id
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 1, '')
        ) AS name_search
    FROM docketwatch.dbo.celebrities c
    LEFT JOIN docketwatch.dbo.celebrity_external_links e 
        ON e.fk_celebrity = c.id AND e.source = 'Wikidata'
    LEFT JOIN docketwatch.dbo.case_celebrity_matches cm 
        ON cm.fk_celebrity = c.id AND cm.match_status <> 'Removed'
    WHERE c.isdeleted = 0
    GROUP BY c.id, c.name, c.priority_score, c.relevancy_index, c.verified, e.external_id
</cfquery>


<!--- Create an empty array --->
<cfset data = []>
<cfloop query="qCelebs">
    <cfset row = {
        "id": qCelebs.celeb_id,
        "name": qCelebs.celebrity_name,
        "priorityScore": qCelebs.priority_score,
        "relevancyIndex": qCelebs.relevancy_index,
        "verified": qCelebs.verified,
        "wikiId": qCelebs.wiki_id,
        "caseCount": qCelebs.case_count,
        "name_search": qCelebs.name_search
    }>
    <cfset arrayAppend(data, row)>
</cfloop>

<cfoutput>#serializeJSON(data)#</cfoutput>