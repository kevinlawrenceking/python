<cfcomponent>
    <!--- Application name (change as needed) --->
    <cfset this.name = "DocketWatchTranscriptApp">
    <!--- Session and application management --->
    <cfset this.sessionManagement = true>
    <cfset this.applicationTimeout = createTimeSpan(1,0,0,0)>  
    <cfset this.sessionTimeout = createTimeSpan(0,2,0,0)>     
    <cfset this.clientManagement = false>

    <cffunction name="onApplicationStart" returnType="boolean" output="false">
        <cfreturn true>
    </cffunction>

    <cffunction name="onSessionStart" returnType="void" output="false">
 
    </cffunction>
</cfcomponent>
