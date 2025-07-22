<cfquery name="getPDFs" datasource="reach">
    SELECT 
        pacer_doc_id,
        CAST(pacer_doc_id AS VARCHAR) + '.pdf' AS new_local_pdf_filename,
        local_pdf_filename
    FROM docketwatch.dbo.case_events_pdf
    WHERE local_pdf_filename IS NOT NULL
</cfquery>

<cfset baseDir = "U:\TMZTOOLS\mediaroot\pacer_pdfs">

<cfloop query="getPDFs">
    <cfset oldFile = baseDir & "\" & getPDFs.local_pdf_filename>
    <cfset newFile = baseDir & "\" & getPDFs.new_local_pdf_filename>

    <cfif fileExists(oldFile)>
        <cffile action="rename"
            source = "#oldFile#"
            destination = "#newFile#">
        <cfoutput>Renamed #getPDFs.local_pdf_filename# → #getPDFs.new_local_pdf_filename#<br></cfoutput>
    <cfelse>
        <cfoutput><span style="color:red;">Missing file: #getPDFs.local_pdf_filename#</span><br></cfoutput>
    </cfif>
</cfloop>
