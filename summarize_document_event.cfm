
<cfset startTime = now()>
<cfset status = 'Pending'>
<cfset filename_cfm = GetFileFromPath(GetTemplatePath())>
<cfset current_filename = ListFirst(filename_cfm, ".")>
<cfset filename_python = current_filename & ".py">
<cfset filename_bat = current_filename & ".bat">
<cfset taskRunID = 0>
<cfparam name="queryString" default="" > 


<cfset rawValue = "F686AF0F-707F-4A36-9BA0-&">
<cfset batFilePath = ExpandPath("python/" & filename_bat)>

<cfoutput>
    <cfexecute name="#batFilePath#"
               arguments="#rawValue#"
               timeout="99999"
               variable="output"
               errorVariable="errorOutput">
    </cfexecute>
</cfoutput>