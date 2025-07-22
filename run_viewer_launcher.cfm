<cfparam name="doc_name" default="">
<cfparam name="key" default="">
<cfparam name="end" default="">

<cfset batPath = "U:\TMZTOOLS\python\launch_viewer.bat">
<cfset args = "#doc_name# #key# #end#">

<cfexecute name="#batPath#"
           arguments="#args#"
           timeout="10"
           variable="output"
           errorVariable="errorOutput">
</cfexecute>

<cfoutput>
<h4>Viewer launch triggered.</h4>
<p>If the PDF doesnt appear, check for login issues or blocked popups.</p>
</cfoutput>
