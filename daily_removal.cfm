
<!--- Update older cases (only those under Review, not matched in case_celebrity_matches, and created before today) --->
<cfquery name="updCases" datasource="Reach" result="updResult">
    UPDATE [docketwatch].[dbo].[cases]
    SET 
         status_notes = 'Daily removal performed on ' + CONVERT(varchar(10), GETDATE(), 120) + '. Removed by daily_removal.cfm.',
         [status] = 'Removed'
    WHERE [status] = 'Review'
      AND [id] NOT IN (
          SELECT [fk_case]
          FROM [docketwatch].[dbo].[case_celebrity_matches]
      )
      AND [created_at] < CAST(GETDATE() AS DATE);
</cfquery>

<cfscript>
    myDatetime = dateformat(Now(),'mm-dd-yyyy');
</cfscript>

<Cfset details = "Daily removal updated " & updResult.recordCount & " records on " & mydatetime />
<!--- Insert a log entry with the total changes --->
<cfquery datasource="Reach">
    INSERT INTO docketwatch.dbo.task_log (created_at, task_name, source, status, details)
    VALUES (
        GETDATE(),
        'Daily Removal',
        'daily_removal.cfm',
        'Completed',
        '#details#'
    );
</cfquery>

<cfoutput>{"status": "completed", "updatedRecords": "#updResult.recordCount#"}</cfoutput>
