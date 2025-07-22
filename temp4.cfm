<cfquery name="getPDFs" datasource="reach">
    SELECT 
        id,
        pacer_doc_id,
        CAST(pacer_doc_id AS VARCHAR) + '.pdf' AS new_local_pdf_filename
    FROM docketwatch.dbo.case_events_pdf
    WHERE local_pdf_filename IS NOT NULL
</cfquery>

<cfset baseDir = "U:\TMZTOOLS\mediaroot\pacer_pdfs">

<cfloop query="getPDFs">
    <cfset newFilePath = baseDir & "\" & getPDFs.new_local_pdf_filename>

    <cfif fileExists(newFilePath)>
        <!--- Update the database with the new filename --->
        <cfquery datasource="reach">
            UPDATE docketwatch.dbo.case_events_pdf
            SET local_pdf_filename = <cfqueryparam value="#getPDFs.new_local_pdf_filename#" cfsqltype="cf_sql_varchar">
            WHERE id = <cfqueryparam value="#getPDFs.id#" cfsqltype="cf_sql_char">
        </cfquery>
        <cfoutput>Updated DB: #getPDFs.new_local_pdf_filename#<br></cfoutput>
    <cfelse>
        <cfoutput><span style="color:red;">Missing file: #getPDFs.new_local_pdf_filename#</span><br></cfoutput>
    </cfif>
</cfloop>
