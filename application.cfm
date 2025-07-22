<cfapplication name="DocketWatch" sessionmanagement="true">

<!--- Determine environment based on CGI server name --->
<cfscript>
    // Get the server name from CGI
    serverName = cgi.server_name;
    
    // Set environment variables based on server name
    if (serverName contains "docketwatch") {
        application.serverDomain = "docketwatch.tmz.local";
        application.fileSharePath = "\\10.146.176.84\general\DOCKETWATCH\";
        application.appType = "docketwatch";
    } else {
        application.serverDomain = "tmztools.tmz.local";
        application.fileSharePath = "\\10.146.176.84\general\TMZTOOLS\wwwroot\";
        application.appType = "tmztools";
    }
    
    // Log which environment we're using (helpful for debugging)
    writeLog(file="docketwatch", text="Application started in environment: #application.appType# on server: #serverName#");
    
    // Set site title based on environment
    application.siteTitle = application.appType eq "docketwatch" ? "DocketWatch" : "TMZ Tools";
    
    // Set web root for relative paths
    application.webRoot = "./";
</cfscript>

<!--- another check --->