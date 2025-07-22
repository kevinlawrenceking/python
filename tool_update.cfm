<cfquery name="missingCases" datasource="Reach">
    SELECT id, fk_case, fk_tool, tool_case_name AS case_name, tool_case_number AS case_number, case_url
    FROM docketwatch.dbo.tool_cases
    WHERE fk_case NOT IN (SELECT id FROM docketwatch.dbo.cases)
</cfquery>

<cfloop query="missingCases">
    <!--- Insert new case --->
    <cfquery name="insertCase" datasource="Reach">
        INSERT INTO docketwatch.dbo.cases (
            case_number, case_name, status, case_url, created_at, owner
        )
        OUTPUT INSERTED.id
        VALUES (
            <cfqueryparam value="#case_number#" cfsqltype="cf_sql_varchar">,
            <cfqueryparam value="#case_name#" cfsqltype="cf_sql_varchar">,
            'Active',
            <cfqueryparam value="#case_url#" cfsqltype="cf_sql_varchar">,
            GETDATE(),
            'system'
        )
    </cfquery>
</cfloop>

  <cfquery datasource="Reach">
UPDATE c
SET c.fk_tool = t.fk_tool
FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.tool_cases t ON t.fk_case = c.id;
</cfquery>


<cfquery datasource="Reach">
update docketwatch.dbo.cases set fk_tool = 6 where id in (
SELECT c.id
FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.courts ct ON c.fk_court = ct.court_code
INNER JOIN docketwatch.dbo.counties co ON ct.fk_county = co.id
 where  c.fk_tool is null and co.state_code = 'CA')
</cfquery>

<cfquery datasource="Reach">
update docketwatch.dbo.cases set fk_tool = 7 where id in (
SELECT c.id
FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.courts ct ON c.fk_court = ct.court_code
INNER JOIN docketwatch.dbo.counties co ON ct.fk_county = co.id
 where  c.fk_tool is null and co.state_code = 'NY')
</cfquery>

<cfquery datasource="Reach">
update docketwatch.dbo.cases set fk_tool = 2 where id in (
SELECT c.id
FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.courts ct ON c.fk_court = ct.court_code
INNER JOIN docketwatch.dbo.counties co ON ct.fk_county = co.id
 where  c.fk_tool is null and co.state_code = 'US')
</cfquery>


<cfquery datasource="Reach">
update docketwatch.dbo.cases set fk_tool = 8 where id in (
SELECT c.id
FROM docketwatch.dbo.cases c
INNER JOIN docketwatch.dbo.courts ct ON c.fk_court = ct.court_code
INNER JOIN docketwatch.dbo.counties co ON ct.fk_county = co.id
 where  c.fk_tool is null and co.state_code NOT IN ('US','CA','NY'))
</cfquery>

