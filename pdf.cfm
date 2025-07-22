<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Transcript Highlights</title>
  <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">

<!--- File Upload Form --->
<div class="container mt-5">
  <div class="row justify-content-center">
    <div class="col-md-6">
      <div class="card shadow">
        <div class="card-header bg-dark text-white">
          <h4 class="mb-0">Extract Transcript Highlights</h4>
        </div>
        <div class="card-body">
          <form method="post" enctype="multipart/form-data">
            <div class="mb-3">
              <label for="transcript" class="form-label">Upload Court Transcript PDF</label>
              <input class="form-control" type="file" name="transcript" id="transcript" accept=".pdf" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">Upload & Extract</button>
          </form>
        </div>
      </div>

      <!--- Handle Form Submission and Results --->
      <cfif structKeyExists(form, "transcript")>
        <cfset uploadDir = expandPath("./uploads/")>
        <cfset outputDir = expandPath("./outputs/")>
        <cfset outputFile = "outputs/#createUUID()#_highlights.pdf">
        <cfset uploadedFile = fileUpload(uploadDir, "transcript", "application/pdf", "makeUnique")>
        <cfset uploadedPath = uploadDir & uploadedFile.serverFile>
        <cfset outputPath = outputDir & listLast(outputFile, "/")>
        <cfset errorOutput = "">
        <cfset pyResult = "">

        <!--- Run the batch file with quoted arguments (handles spaces) --->
        <cftry>
          <cfexecute name="U:\TMZTOOLS\python\pdf.bat"
            arguments='"#uploadedPath#" "#outputPath#"'
            variable="pyResult"
            errorVariable="errorOutput"
            timeout="120">
          </cfexecute>

          <!--- Show Results --->
          <cfif fileExists(outputPath)>
            <div class="alert alert-success mt-4">
              <strong>Done!</strong>
             <Cfoutput> <a href="outputs/#listLast(outputPath, '\')#" target="_blank">Download highlighted PDF</a></cfoutput>
            </div>
          <cfelse>
            <div class="alert alert-danger mt-4">
              <strong>Error:</strong> Highlighted PDF was not generated.<br>
              <cfif len(pyResult)>
               <Cfoutput> <div><strong>Python Output:</strong> <pre>#encodeForHtml(pyResult)#</pre></div></cfoutput>
              </cfif>
              <cfif len(errorOutput)>
              <Cfoutput>  <div><strong>Python Error:</strong> <pre>#encodeForHtml(errorOutput)#</pre></div></cfoutput>
              </cfif>
            </div>
          </cfif>
<Cfif #isdefined('dbug')#>
          <!--- Debug Output --->
          <cfoutput>
            <div class="alert alert-secondary mt-4">
              <strong>Debug Info:</strong><br>
              uploadDir = #uploadDir#<br>
              outputDir = #outputDir#<br>
              uploadedFile.serverFile = #uploadedFile.serverFile#<br>
              uploadedPath = #uploadedPath#<br>
              outputPath = #outputPath#<br>
            </div>
          </cfoutput>
          </cfif>
          <cfcatch>
            <div class="alert alert-danger mt-4">
              <strong>Batch/Python Exception:</strong>
              <pre>#encodeForHtml(cfcatch.message)#<br>#encodeForHtml(cfcatch.detail)#</pre>
            </div>
          </cfcatch>
        </cftry>
      </cfif>
    </div>
  </div>
</div>

<cfinclude template="footer_script.cfm">
</body>
</html>
