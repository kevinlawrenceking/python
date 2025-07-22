<cfset insertedCount = 0>

<!--- Query to Fetch Celebrities from DAMZ --->
<cfquery name="damzCelebs" datasource="reach">
 SELECT  p.id, count(*) as appearances,
            REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '') AS celebrity_name
        FROM [damz].[dbo].[asset_metadata] m
		INNER JOIN [damz].[dbo].[asset] a ON a.id = m.fk_asset
		INNER JOIN [damz].[dbo].[picklist_celebrity] p on p.name = REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '') 
        WHERE a.created_at >= DATEADD(YEAR, -5, GETDATE())  
          AND m.celebrity_in_photo IS NOT NULL 
          AND m.celebrity_in_photo <> '[]' 
          AND m.celebrity_in_photo <> '["Not Applicable"]'
		  group by p.id, m.celebrity_in_photo
		  having COUNT(*) > 1 and p.id not in (
SELECT  [id]
      
  FROM [docketwatch].[dbo].[celebrities]

          )
</cfquery>

<!--- Loop Through the DAMZ Celebs and Insert into DocketWatch ---> 
<cfloop query="damzCelebs">
    <cfset celebID = damzCelebs.id>
    <cfset celebName = damzCelebs.celebrity_name>
    <cfset celebAppearances = damzCelebs.appearances>

    <!--- Insert Celeb into DocketWatch if Not Already Exists --->
    <cfquery datasource="Reach">
        INSERT INTO docketwatch.dbo.celebrities (id, name, appearances)
        SELECT TOP 100
            <cfqueryparam value="#celebID#" cfsqltype="cf_sql_varchar">, 
            <cfqueryparam value="#celebName#" cfsqltype="cf_sql_varchar">, 
            <cfqueryparam value="#celebAppearances#" cfsqltype="cf_sql_integer">
        WHERE NOT EXISTS (
            SELECT 1 FROM docketwatch.dbo.celebrities WHERE id = <cfqueryparam value="#celebID#" cfsqltype="cf_sql_varchar">
        )
    </cfquery>

    <cfset insertedCount++>
</cfloop>

<!--- Output Summary ---> 
<cfoutput>
    Inserted #insertedCount# new celebrities from DAMZ into DocketWatch.
</cfoutput>