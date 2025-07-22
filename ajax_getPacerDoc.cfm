<cfsetting showdebugoutput="false">

<!---
    This script handles the AJAX request from the case details page to download a PDF from PACER.
    It validates incoming parameters, securely calls a Python script to do the actual download,
    updates the database with the result, and returns a JSON response to the browser.
--->

<cfparam name="form.docID" type="string">
<cfparam name="form.eventURL" type="string">
<cfparam name="form.caseID" type="string">

<cfset response = {
    STATUS = "ERROR",
    MESSAGE = "An unknown error occurred.",
    FILEPATH = ""
}>

<cftry>
    <!--- Define full, absolute paths for the Python executable and your script --->
    <cfset pythonExecutable = "C:\Program Files\Python312\python.exe">
    <cfset pythonScriptPath = "#application.fileSharePath#python\download_pacer_pdf.py">
    <!---
        Define the folder where PDFs will be saved and create a consistent filename.
        Ensure this folder exists and the ColdFusion user has write permissions to it.
    --->
    <cfset pdfSaveFolder = "#application.fileSharePath#python\pacer_docs\">
    <cfset pdfFilename = "case_#form.caseID#_doc_#form.docID#.pdf">
    <cfset fullPdfPath = pdfSaveFolder & pdfFilename>
    <cfset webAccessiblePath = "/pacer_docs/#pdfFilename#"> <!--- Assuming this network path is mapped to a web-accessible directory --->

    <!---
        Build the command line arguments.
        THE FIX: The python script path MUST be the first argument.
    --->
    <cfset scriptArgs = [pythonScriptPath, form.eventURL, fullPdfPath]>

    <!--- Execute the Python script --->
    <cfexecute
        name="#pythonExecutable#"
        arguments="#scriptArgs#"
        variable="pythonOutput"
        timeout="9999"
        errorVariable="pythonError"
    />

    <cfif len(trim(pythonError))>
        <!--- Catches errors from the Python execution environment itself --->
        <cfset response.MESSAGE = "Python execution error: #HtmlEditFormat(pythonError)#">
    <cfelse>
        <!--- The Python script should print a JSON string on success/failure --->
        <cftry>
            <cfset pythonResponse = DeserializeJSON(pythonOutput)>

            <cfif pythonResponse.status EQ "success">
                <cfset response.STATUS = "SUCCESS">
                <cfset response.MESSAGE = "PDF downloaded successfully.">
                <cfset response.FILEPATH = webAccessiblePath>

                <!--- Update the database to mark the document as downloaded and save the local filename. --->
                <cfquery datasource="your_dsn_name">
                    UPDATE docketwatch.dbo.case_events
                    SET
                        isDownloaded = 1,
                        local_pdf_filename = <cfqueryparam value="#pdfFilename#" cfsqltype="cf_sql_varchar">
                    WHERE id = <cfqueryparam value="#form.docID#" cfsqltype="cf_sql_integer"> <!--- Assuming your PK is named 'id' --->
                </cfquery>

            <cfelse>
                <!--- The script ran, but reported a failure (e.g., auth failed, link broken) --->
                <cfset response.MESSAGE = "Python script failed: #HtmlEditFormat(pythonResponse.message)#">
            </cfif>
            <cfcatch type="json">
                 <cfset response.MESSAGE = "Failed to parse JSON response from Python script. Output: #HtmlEditFormat(pythonOutput)#">
            </cfcatch>
        </cftry>
    </cfif>

    <cfcatch type="any">
        <cfset response.MESSAGE = "A ColdFusion error occurred: #HtmlEditFormat(cfcatch.Message)#">
    </cfcatch>
</cftry>

<!--- Return the final JSON response to the browser's AJAX call --->
<cfcontent type="application/json">
<cfoutput>#SerializeJSON(response)#</cfoutput>
