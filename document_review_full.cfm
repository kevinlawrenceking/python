<cfparam name="url.doc_uid" default="">
<cfif NOT len(url.doc_uid)>
    <h2>Error: No doc_uid provided.</h2>
    <cfabort>
</cfif>


  <cfquery name="getDoc" datasource="Reach">
    SELECT TOP 1
        d.doc_uid,
        d.fk_case,
        e.event_no,
        d.fk_case_event,
        d.ocr_text_raw,
        d.ocr_text,
        d.search_text,
        d.summary_ai,
        d.summary_ai_html,
        d.ai_processed_at,
        c.case_name,
        e.event_description,

        CAST(d.doc_id AS VARCHAR) + '.pdf' AS file_name,

        -- Constructed virtual HTTP link
        'http://#application.serverDomain#/docs/cases/' + 
            CAST(d.fk_case AS VARCHAR) + '/' + 
            CAST(d.doc_id AS VARCHAR) + '.pdf' AS http_url,

        -- Constructed file system path
        '\\10.146.176.84\general\DOCKETWATCH\docs\cases\' + 
            CAST(d.fk_case AS VARCHAR) + '\' + 
            CAST(d.doc_id AS VARCHAR) + '.pdf' AS local_path

    FROM docketwatch.dbo.documents d
    LEFT JOIN docketwatch.dbo.cases c ON d.fk_case = c.id
    LEFT JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
    WHERE d.doc_uid = <cfqueryparam cfsqltype="cf_sql_varchar" value="#url.doc_uid#">
</cfquery>

<cfquery name="docList" datasource="Reach">
    SELECT TOP 20 doc_id, doc_uid
    FROM docketwatch.dbo.documents
    WHERE ocr_text_raw IS NOT NULL
    ORDER BY ai_processed_at DESC
</cfquery>

<cfif getDoc.recordCount EQ 0>
    <h2>No document found with UID: <cfoutput>#url.doc_uid#</cfoutput></h2>
    <cfabort>
</cfif>



<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><cfoutput>Document Review</cfoutput></title>
    <cfinclude template="head.cfm"> <!--- Includes Bootstrap & DataTables CSS --->
</head>
<body>

<<div class="container-fluid mt-3">
    <div class="row">

        <!--- Sidebar: List of Doc IDs --->
        <div class="col-md-2">
            <h5>Recent Docs</h5>
            <ul class="list-group">
                <cfoutput query="docList">
                    <li class="list-group-item <cfif doc_uid EQ url.doc_uid>active</cfif>">
                        <a href="document_review.cfm?doc_uid=#doc_uid#" style="text-decoration:none; color:inherit;">
                            #doc_id#
                        </a>
                    </li>
                </cfoutput>
            </ul>
        </div>

        <!--- Main Content --->
        <div class="col-md-10">
            <cfoutput>
                <h1>Document Review</h1>

                <h4>Case: #getDoc.case_name# - [#getDoc.event_no#] #getDoc.event_description#</h4>
                <h4>AI Processed At: #getDoc.ai_processed_at#</h4>

                <!--- View Button --->
                <a href="#getDoc.http_url#" target="_blank" class="btn btn-primary mb-3">
                    <i class="fas fa-file-pdf"></i> View Document
                </a>

                <hr>

                <h2>ocr_text_raw</h2>
                <pre style="white-space: pre-wrap; background: ##f9f9f9; padding: 1em; border: 1px solid ##ccc;">
#getDoc.ocr_text_raw#
</pre>

                <h2>ocr_text</h2>
                <pre style="white-space: pre-wrap; background: ##eef9ff; padding: 1em; border: 1px solid ##99c;">
#getDoc.ocr_text#
</pre>

                <h2>search_text</h2>
                <pre style="white-space: pre-wrap; background: ##fef9e7; padding: 1em; border: 1px solid ##cc9;">
#getDoc.search_text#
</pre>

                <h2>summary_ai</h2>
                <pre style="white-space: pre-wrap; background: ##f3f3f3; padding: 1em; border: 1px solid ##999;">
#getDoc.summary_ai#
</pre>

                <h2>summary_ai_html</h2>
                <div style="background: ##fdfdfd; padding: 1em; border: 1px solid ##aaa;">
#getDoc.summary_ai_html#
</div>
            </cfoutput>
        </div>
    </div>
</div>
</body>
</html>
