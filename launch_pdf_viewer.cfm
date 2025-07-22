<cfparam name="doc_name" default="">
<cfparam name="key" default="">
<cfparam name="end" default="">

<cfset viewerUrl = "https://ww2.lacourt.org/documentviewer/v1/?name=#doc_name#&key=#key#&end=#end#">

<!--- Just redirect to the viewer URL (requires active login session) --->
<cflocation url="#viewerUrl#" addtoken="no">
