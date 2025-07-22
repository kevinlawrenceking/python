<cfcontent type="application/json">

<cfquery name="caseTracking" datasource="Reach">
    SELECT 
        ct.court_name AS courthouse,
        p.practice_name AS division,
        cc.last_updated,
        (CAST(cc.yy AS VARCHAR(2)) + cc.fk_court + cc.fk_practice + RIGHT('00000' + CAST(cc.last_number AS VARCHAR(5)), 5)) AS last_court_number,
        COALESCE(COUNT(c.id), 0) AS total_cases
    FROM docketwatch.dbo.case_counter cc
    LEFT JOIN docketwatch.dbo.courts ct ON cc.fk_court = ct.court_code
    LEFT JOIN docketwatch.dbo.practices p ON cc.fk_practice = p.practice_code
    LEFT JOIN docketwatch.dbo.cases c 
        ON LEFT(c.case_number, 6) = CAST(cc.yy AS VARCHAR(2)) + cc.fk_court + cc.fk_practice
    GROUP BY ct.court_name, p.practice_name, cc.last_updated, cc.yy, cc.fk_court, cc.fk_practice, cc.last_number
    ORDER BY cc.last_updated DESC;
</cfquery>

<cfset data = []>
<cfloop query="caseTracking">
    <cfset row = {
        "courthouse": caseTracking.courthouse,
        "division": caseTracking.division,
        "last_updated": caseTracking.last_updated,
        "last_court_number": caseTracking.last_court_number,
        "total_cases": caseTracking.total_cases
    }>
    <cfset arrayAppend(data, row)>
</cfloop>

<cfoutput>#serializeJSON(data)#</cfoutput>
