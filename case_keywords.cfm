<!--- Fetch Celebrities from DAMZ --->
<cfquery name="damzCelebs" datasource="reach">
    SELECT DISTINCT RTRIM(LTRIM(celebrity_in_photo)) AS celebrity_name
    FROM [damz].[dbo].[asset_metadata]
    WHERE 
        (full_text LIKE '%court%' OR full_text LIKE '%trial%' OR full_text LIKE '%lawsuit%' 
         OR full_text LIKE '%arrest%' OR full_text LIKE '%charged%' OR full_text LIKE '%indicted%'
         OR full_text LIKE '%settlement%' OR full_text LIKE '%convicted%' OR full_text LIKE '%plea deal%'
         OR full_text LIKE '%hearing%' OR full_text LIKE '%verdict%' OR full_text LIKE '%sentencing%'
         OR full_text LIKE '%judge%' OR full_text LIKE '%jury%' OR full_text LIKE '%attorney%'
         OR full_text LIKE '%prosecutor%' OR full_text LIKE '%defendant%' OR full_text LIKE '%plaintiff%'
         OR full_text LIKE '%subpoena%' OR full_text LIKE '%warrant%' OR full_text LIKE '%felony%'
         OR full_text LIKE '%misdemeanor%' OR full_text LIKE '%investigation%' OR full_text LIKE '%allegations%'
         OR full_text LIKE '%testimony%')
        AND NOT (full_text LIKE '%basketball%' OR full_text LIKE '%tennis%' OR full_text LIKE '%soccer%' 
                 OR full_text LIKE '%football%' OR full_text LIKE '%hockey%' OR full_text LIKE '%golf%' 
                 OR full_text LIKE '%baseball%' OR full_text LIKE '%stadium%' OR full_text LIKE '%match%'
                 OR full_text LIKE '%finals%' OR full_text LIKE '%championship%')
    ORDER BY celebrity_name;
</cfquery>

<!--- Batch Update `docketwatch` --->
<cfif damzCelebs.recordCount gt 0>
    <cfset celebList = ValueList(damzCelebs.celebrity_name)>

    <cfquery datasource="Reach">
        UPDATE docketwatch.dbo.celebrities
        SET case_keywords = 1
        WHERE [name] IN (<cfqueryparam value="#celebList#" cfsqltype="cf_sql_varchar" list="true">)
    </cfquery>

    <cfoutput>
        <p>Updated <strong>#damzCelebs.recordCount#</strong> celebrities in docketwatch.</p>
    </cfoutput>
<cfelse>
    <cfoutput>
        <p>No relevant celebrities found.</p>
    </cfoutput>
</cfif>
