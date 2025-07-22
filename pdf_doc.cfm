<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Transcript Highlights</title>
  <cfinclude template="head.cfm">

  <style>
.dropzone {
  border: 2px dashed #007bff;
  border-radius: 8px;
  background: #f8f9fa;
  padding: 2rem 1rem;
  text-align: center;
  color: #6c757d;
  cursor: pointer;
  transition: background 0.2s, border 0.2s;
}
.dropzone.dragover {
  background: #e2e6ea;
  border-color: #0056b3;
}
.dropzone input[type="file"] {
  display: none;
}
</style>

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
        <!---    <div class="mb-3">
              <label for="transcript" class="form-label">Upload Court Transcript PDF</label>
              <input class="form-control" type="file" name="transcript" id="transcript" accept=".pdf" required>
            </div> --->

            <div class="mb-3">
  <label for="transcript" class="form-label">Upload Court Transcript PDF</label>
  <div id="dropzone" class="dropzone">
    <span id="dropzone-text">Drag & drop a PDF here, or click to browse</span>
    <input class="form-control" type="file" name="transcript" id="transcript" accept=".pdf" required>
  </div>
</div>


            <button type="submit" class="btn btn-primary w-100">Upload & Extract</button>
          </form>
        </div>
      </div>

      <!--- Handle Form Submission and Results --->
      <cfif structKeyExists(form, "transcript")>
        <cfset uploadDir = expandPath("./uploads/")>
        <cfset outputDir = expandPath("./outputs/")>
        <cfset outputFile = "outputs/#createUUID()#_highlights.doc">
        <cfset uploadedFile = fileUpload(uploadDir, "transcript", "application/pdf", "makeUnique")>
        <cfset uploadedPath = uploadDir & uploadedFile.serverFile>
        <cfset outputPath = outputDir & listLast(outputFile, "/")>
        <cfset errorOutput = "">
        <cfset pyResult = "">

        <!--- Run the batch file with quoted arguments (handles spaces) --->
        <cftry>
          <cfexecute name="U:\TMZTOOLS\python\pdf_doc.bat"
            arguments='"#uploadedPath#" "#outputPath#"'
            variable="pyResult"
            errorVariable="errorOutput"
            timeout="120">
          </cfexecute>

          <!--- Show Results --->
          <cfif fileExists(outputPath)>
            <div class="alert alert-success mt-4">
              <strong>Done!</strong>
             <Cfoutput> <a href="outputs/#listLast(outputPath, '\')#" target="_blank">DOWNLOAD DOCUMENT</a></cfoutput>
            </div>
          <cfelse>
            <div class="alert alert-danger mt-4">
              <strong>Error:</strong> Highlighted DOC was not generated.<br>
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

<script>
document.addEventListener('DOMContentLoaded', function() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('transcript');
  const text = document.getElementById('dropzone-text');

  // Open file browser on click
  dropzone.addEventListener('click', function() {
    fileInput.click();
  });

  // Show selected file name
  fileInput.addEventListener('change', function() {
    if (fileInput.files.length) {
      text.textContent = fileInput.files[0].name;
    } else {
      text.textContent = 'Drag & drop a PDF here, or click to browse';
    }
  });

  // Drag & drop functionality
  dropzone.addEventListener('dragover', function(e) {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', function(e) {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      text.textContent = fileInput.files[0].name;
    }
  });
});
</script>

</body>
</html>
