<cfset fk_user = getauthuser()>
<cfset subscribers_tab_status = "">

<cfquery name="case_details" datasource="Reach">
    SELECT [id],
           [case_number],
           [case_name],
           [notes] AS details,
           [last_updated],
           [owner],
           [created_at],
           [status],
           ISNULL([case_type], 'Unknown') AS case_type,
           [case_url],
           fk_court AS court_code,
           court_name_pacer,
           [summarize_html]
    FROM [docketwatch].[dbo].[cases]
    WHERE id = <cfqueryparam value="#url.id#" cfsqltype="cf_sql_integer">
</cfquery>

<cfquery name="subscribers" datasource="Reach">
SELECT r.id,
u.firstname + ' ' + u.lastname as fullname,
u.firstname,
u.lastname,
u.email,
u.userRole

  FROM [docketwatch].[dbo].[case_email_recipients] r

  inner join [docketwatch].[dbo].[users] u on u.username = r.fk_username
    WHERE r.fk_case = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer"> and r.notify = 1
    ORDER BY u.lastname, u.firstname
</cfquery>

<cfquery name="eligible_users" datasource="Reach">
    SELECT 
        u.username AS id,
        u.firstname + ' ' + u.lastname AS display
    FROM docketwatch.dbo.users u
    WHERE u.username NOT IN (
        SELECT r.fk_username
        FROM docketwatch.dbo.case_email_recipients r
        WHERE r.fk_case = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer">
    )
    ORDER BY u.lastname, u.firstname
</cfquery>


<cfquery name="courthouse" datasource="Reach">
    SELECT c.[court_code],
           c.[court_name],
           c.[address],
           c.[city],
           c.[state],
           c.[zip],
           ISNULL(c.[image_location], '../services/courthouse.png') AS image_url,
           o.[name] AS county_name,
           c.[court_id],
           c.[court_url],
           c.[last_scraped]
    FROM [docketwatch].[dbo].[courts] c
    INNER JOIN [docketwatch].[dbo].[counties] o ON c.fk_county = o.id
    WHERE c.court_code = <cfqueryparam value="#case_details.court_code#" cfsqltype="cf_sql_varchar">
</cfquery>

<cfquery name="dockets" datasource="Reach">
SELECT 
    e.[event_no],
    e.[id],
    e.[event_date],
    e.[event_description],
    e.[additional_information],
    e.[created_at],
    e.[status],
    p.[pdf_title],
    e.[event_result],
    e.[party_type],
    e.[party_number],
    e.[amount],
    e.[fk_cases],
    e.[fk_task_run_log],
    e.[additional_information],
    e.[emailed],
    e.[summarize],
    e.[tmz_summarize],
    e.[event_url],
    e.[isDoc],
    p.[isDownloaded],
    p.[local_pdf_filename], -- main docket PDF

    -- HTML anchor tags for each attachment
    (
        SELECT STUFF((
            SELECT 
                ' <a href="/mediaroot/pacer_pdfs/' + ap.local_pdf_filename + '" target="_blank" class="btn btn-sm btn-outline-secondary" title="' + 
                ISNULL(REPLACE(ap.pdf_title, '"', ''), 'Exhibit') + 
                '"><i class=''fas fa-paperclip''></i></a>'
            FROM docketwatch.dbo.case_events_pdf ap
            WHERE ap.fk_case_event = e.id
              AND ap.pdf_type = 'Attachment'
              AND ap.isDownloaded = 1
              AND ap.local_pdf_filename IS NOT NULL order by ap.pdf_no 
            FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 1, '')
    ) AS attachment_links

FROM docketwatch.dbo.case_events e

-- Main docket PDF (single)
LEFT JOIN docketwatch.dbo.case_events_pdf p 
    ON e.id = p.fk_case_event AND p.pdf_type = 'Docket'

WHERE e.fk_cases = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer">
ORDER BY e.created_at DESC



</cfquery>

<cfquery name="hearings" datasource="Reach">
    SELECT h.[ID],
           h.[fk_case],
           d.[name] AS department,
           h.[hearing_type] AS type,
           h.[case_utype_description] AS description,
           h.[hearing_datetime] AS date,
           h.[hearing_datetime] AS time
    FROM [docketwatch].[dbo].[hearings] h
    LEFT JOIN [docketwatch].[dbo].[departments] d ON d.id = h.fk_department
    WHERE h.fk_case = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer">
    ORDER BY h.[hearing_datetime] DESC
</cfquery>

<cfquery name="logs" datasource="Reach">
SELECT  
    COUNT(*) as cnt,
    r.timestamp_started, 
    r.timestamp_ended,
    r.status,
    r.summary,
    r.created_at,
 s.task_name,
    DATEDIFF(MINUTE, r.timestamp_started, r.timestamp_ended) AS duration_minutes,
 
    DATEDIFF(SECOND, r.timestamp_started, r.timestamp_ended) AS duration_seconds,
 
    RIGHT('0' + CAST(DATEDIFF(MINUTE, r.timestamp_started, r.timestamp_ended) AS VARCHAR), 2) + ':' +
    RIGHT('0' + CAST(DATEDIFF(SECOND, r.timestamp_started, r.timestamp_ended) % 60 AS VARCHAR), 2) AS duration_mmss
FROM docketwatch.dbo.task_runs_log l
INNER JOIN docketwatch.dbo.task_runs r ON r.id = l.fk_task_run
INNER JOIN docketwatch.dbo.cases c ON c.id = l.fk_case
INNER JOIN docketwatch.dbo.scheduled_task s ON s.id = r.fk_scheduled_task
WHERE c.id = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer">
GROUP BY  
    r.timestamp_started, 
    r.timestamp_ended,
    r.status,
    r.summary,
    s.task_name,
    r.created_at
ORDER BY r.created_at DESC

</cfquery>

<cfquery name="celebrities" datasource="Reach">
    SELECT 
        m.[id],
        c.id as celebrity_id,
        c.name AS celebrity_name,
        a.name AS legal_name,
        m.[probability_score],
        m.[priority_score],
        m.[ranking_score],
        m.match_status
    FROM [docketwatch].[dbo].[case_celebrity_matches] m
    INNER JOIN [docketwatch].[dbo].[celebrities] c ON c.id = m.fk_celebrity
    LEFT JOIN [docketwatch].[dbo].[celebrity_names] a 
        ON a.fk_celebrity = c.id AND a.type = 'Legal'
    WHERE m.fk_case = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer">
    AND m.match_status <> <cfqueryparam value="Removed" cfsqltype="cf_sql_varchar">
</cfquery>


<cfquery name="links" datasource="reach">
    SELECT 
        id,
        fk_case,
        case_url,
        title,
        category,
        created_at,
        fk_user,
        isActive
    FROM docketwatch.dbo.case_links
    WHERE fk_case = <cfqueryparam value="#case_details.id#" cfsqltype="cf_sql_integer"> and isactive = 1
</cfquery>


<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><cfoutput>Case Details - #case_details.case_number#</cfoutput></title>
    <cfinclude template="head.cfm"> <!--- Includes Bootstrap & DataTables CSS --->
</head>
<body>

<cfinclude template="navbar.cfm"> <!--- Navigation Bar --->

<div class="container mt-4">
  <div class="d-flex align-items-center mb-3">
    <h2 class="mb-0">Case Details</h2>
    <div class="d-flex gap-2 ms-auto">
      <a href="case_update.cfm?id=<cfoutput>#case_details.id#</cfoutput>" class="btn btn-primary" style="color:white;">
        <i class="bi bi-pencil"></i> update
      </a>
      <a href="" class="btn btn-secondary" style="color:white;">
        <i class="bi bi-arrow-left"></i> Back
      </a>
    </div>
</div>

    <cfoutput>
    <div class="row gx-4"> <!--- Bootstrap Row with horizontal gutter --->

        <!--- Case Detail Section --->
        <div class="col-12 col-xl-6">
            <div class="card shadow-sm mb-4">
                <div class="card-body">
                           <h5 class="card-title mb-3">
                        #case_details.case_number# - #case_details.case_name#
                        <a href="#case_details.case_url#" target="_blank" class="ms-2 text-decoration-none" title="View full case">
                            <i class="bi bi-search" style="font-size: 1.2rem;"></i>
                        </a>
                    </h5>

                    <dl class="row mb-0">
<dt class="col-sm-4">Status</dt>
<dd class="col-sm-8">
    <span id="currentStatus"><strong>#case_details.status#</strong></span>

 
        <cfif case_details.status EQ "Review">
            <button class="btn btn-sm btn-outline-danger ms-2" onclick="updateCaseStatus(#case_details.id#, 'Removed')">Remove</button>
            <button class="btn btn-sm btn-outline-success ms-2" onclick="updateCaseStatus(#case_details.id#, 'Tracked')">Track</button>
        <cfelseif case_details.status EQ "Tracked">
            <button class="btn btn-sm btn-outline-secondary ms-2" onclick="updateCaseStatus(#case_details.id#, 'Review')">Set to Review</button>
            <button class="btn btn-sm btn-outline-danger ms-2" onclick="updateCaseStatus(#case_details.id#, 'Removed')">Remove</button>
        <cfelseif case_details.status EQ "Removed">
            <button class="btn btn-sm btn-outline-secondary ms-2" onclick="updateCaseStatus(#case_details.id#, 'Review')">Set to Review</button>
            <button class="btn btn-sm btn-outline-success ms-2" onclick="updateCaseStatus(#case_details.id#, 'Tracked')">Track</button>
        </cfif>

</dd>


                        <dt class="col-sm-4">Case Type</dt>
                        <dd class="col-sm-8">#case_details.case_type#</dd>

                        <dt class="col-sm-4">Owner</dt>
                        <dd class="col-sm-8">#case_details.owner#</dd>

                        <dt class="col-sm-4">Created</dt>
                        <dd class="col-sm-8">#dateFormat(case_details.created_at, "mm/dd/yyyy")#</dd>

                        <dt class="col-sm-4">Last Updated</dt>
                        <dd class="col-sm-8">#dateFormat(case_details.last_updated, "mm/dd/yyyy")# at #timeformat(case_details.last_updated)#</dd>

                        <dt class="col-sm-4">Notes / Details</dt>
                        <dd class="col-sm-8">
                            <pre class="mb-0" style="white-space: pre-wrap;">#htmlEditFormat(case_details.details)#</pre>
                        </dd>
                    </dl>
                </div>
            </div>
        </div>

        <!--- Courthouse Info Section --->
        <div class="col-12 col-xl-6">
            <div class="card shadow-sm mb-4">
                <div class="card-body">
                    <h5 class="card-title mb-3">
                        Courthouse Info
                        <cfif len(trim(courthouse.court_url))>
                            <a href="#courthouse.court_url#" target="_blank" class="ms-2 text-decoration-none" title="View Courthouse">
                                <i class="bi bi-search" style="font-size: 1rem;"></i>
                            </a>
                        </cfif>
                    </h5>

                    <Cfif case_details.court_name_pacer neq "">
 <strong>#case_details.court_name_pacer#</strong><br><CFelse>


                    <div class="d-flex align-items-center mb-3">
                        <img src="#courthouse.image_url#" alt="Courthouse" class="rounded-circle me-3" width="50" height="50">
                        <div>
                            <strong>#courthouse.court_name#</strong><br>
                            #courthouse.address#<br>
                            #courthouse.city#, #courthouse.state# #courthouse.zip#
                        </div>
                    </div>

                    <dl class="row mb-0">
                        <dt class="col-sm-4">County</dt>
                        <dd class="col-sm-8">#courthouse.county_name#</dd>

                        <dt class="col-sm-4">Court ID</dt>
                        <dd class="col-sm-8">#courthouse.court_code#</dd>

                    </dl>
                    </cfif>
                </div>
            </div>
        </div>

    </div>
<!--- Set active tab variables --->
<cfset links_tab_status = "">
<cfset dockets_tab_status = "">
<cfset hearings_tab_status = "">
<cfset log_tab_status = "">
<cfset celebrities_tab_status = "">


<!--- Initialize all tab statuses --->
<cfset summary_tab_status = "">
<cfset links_tab_status = "">
<cfset dockets_tab_status = "">
<cfset hearings_tab_status = "">
<cfset log_tab_status = "">
<cfset celebrities_tab_status = "">
<cfset subscribers_tab_status = "">

<!--- Handle tab switching --->
<cfif structKeyExists(url, "tab")>
    <cfset tabName = lcase(trim(url.tab))>
    <cfif listFind("summary,links,dockets,hearings,log,celebrities,alerts", tabName)>
        <cfset "#tabName#_tab_status" = "show active">
    <cfelse>
        <cfset links_tab_status = "show active"> <!--- fallback for invalid tab param --->
    </cfif>
<cfelse>
    <!--- Default priority logic when no tab param --->
    <cfif len(trim(case_details.summarize_html))>
        <cfset summary_tab_status = "show active">
    <cfelseif dockets.recordcount GT 0>
        <cfset dockets_tab_status = "show active">
    <cfelseif hearings.recordcount GT 0>
        <cfset hearings_tab_status = "show active">
    <cfelseif logs.recordcount GT 0>
        <cfset log_tab_status = "show active">
    <cfelseif celebrities.recordcount GT 0>
        <cfset celebrities_tab_status = "show active">
    <cfelse>
        <cfset links_tab_status = "show active">
    </cfif>
</cfif>


<!--- Tabs Section for Dockets, Hearings, Log, Celebrities --->
<div class="card shadow-sm mt-4">
    <div class="card-body">

 <!--- Tab headings --->
<cfoutput>
<ul class="nav nav-tabs" id="caseTabs" role="tablist">
    <cfif len(trim(case_details.summarize_html))>
        <li class="nav-item" role="presentation">
            <a class="nav-link #summary_tab_status#" id="summary-tab" data-bs-toggle="tab" href="##summary" role="tab">Summary</a>
        </li>
    </cfif>
    <li class="nav-item" role="presentation">
        <a class="nav-link #links_tab_status#" id="links-tab" data-bs-toggle="tab" href="##links" role="tab">Links</a>
    </li>
    <li class="nav-item" role="presentation">
        <a class="nav-link #dockets_tab_status#" id="dockets-tab" data-bs-toggle="tab" href="##dockets" role="tab">Dockets</a>
    </li>
    <li class="nav-item" role="presentation">
        <a class="nav-link #hearings_tab_status#" id="hearings-tab" data-bs-toggle="tab" href="##hearings" role="tab">Hearings</a>
    </li>
    <li class="nav-item" role="presentation">
        <a class="nav-link #log_tab_status#" id="log-tab" data-bs-toggle="tab" href="##log" role="tab">Log</a>
    </li>
    <li class="nav-item" role="presentation">
        <a class="nav-link #celebrities_tab_status#" id="celebrities-tab" data-bs-toggle="tab" href="##celebrities" role="tab">Celebrities</a>
    </li>
    <li class="nav-item" role="presentation">
        <a class="nav-link #subscribers_tab_status#" id="alerts-tab" data-bs-toggle="tab" href="##alerts" role="tab">Subscribers</a>
    </li>
</ul>
</cfoutput>

<!--- Tab content panes --->
 

        <div class="tab-content mt-3" id="caseTabsContent">
<cfif len(trim(case_details.summarize_html))>
    <div class="tab-pane p-3 #summary_tab_status#" id="summary" role="tabpanel">
 
        <cfoutput>
            #REReplace(
                case_details.summarize_html,
                "<h3(.*?)>(.*?)</h3>",
                "<h5\1>\2</h5>",
                "all"
            )#
        </cfoutput>
    </div>
</cfif>


<div class="tab-pane p-3  #links_tab_status#" id="links" role="tabpanel">
       <button class="btn btn-primary mb-3" onclick="showAddLinkModal()">
    <i class="bi bi-plus-circle me-1"></i> Add Link
</button>

       <cfif links.recordcount GT 0>
        <table id="linksTable" class="table table-striped table-bordered mt-3">
            <thead class="table-dark">
    <tr>
        <th>Title</th>
        <th>Category</th>
        <th>Created By</th>
        <th>Date Added</th>
        <th>Actions</th> <!--- New column --->
    </tr>
</thead>
<tbody>
    <cfloop query="links">
    <tr>
        <td>
            <a href="#case_url#" target="_blank" class="text-decoration-none">
                #title# <i class="fa-solid fa-up-right-from-square ms-1"></i>
            </a>
        </td>
        <td>#category#</td>
        <td>#fk_user#</td>
        <td>#dateFormat(created_at, "mm/dd/yyyy")#</td>
        <td>
            <button class="btn btn-sm btn-outline-danger" title="Delete" onclick="deleteLink(#id#)">
                <i class="fa-solid fa-trash"></i>
            </button>
        </td>
    </tr>
    </cfloop>
</tbody>

        </table>
        <Cfelse>
        <p>No links associated to this case.</p>
        </cfif>
    </div>




          
            <!--- Dockets Tab --->
    <div class="tab-pane p-3 #dockets_tab_status#" id="dockets" role="tabpanel">
          <cfif dockets.recordcount GT 0>
                <table id="docketTable" class="table table-striped table-bordered mt-3">
                    <thead class="table-dark">
                        <tr>
                            <th>Event No</th>
                            <th>Date</th>
                            <th>Description</th>
                
                                 <th>Actions</th> <!--- New Column for the button --->
                                 
                                 
                                 </tr>
                    </thead>
                    <tbody>
                        <cfloop query="dockets">
                            <tr>
                                <td>#event_no#</td>
                              <td data-order="#dateFormat(event_date, 'yyyy-mm-dd')#">#dateFormat(event_date, 'mm/dd/yyyy')#</td>
 
                                <td>#event_description#</td>
<td nowrap>
    <!--- PDF action buttons container --->
    <div id="button-container-#dockets.id#">
        <!--- View Docket PDF if downloaded --->
        <cfif dockets.isDownloaded EQ 1 AND len(dockets.local_pdf_filename)>
            <a href="/mediaroot/pacer_pdfs/#dockets.local_pdf_filename#"
               target="_blank"
               class="btn btn-sm btn-outline-success"
               title="#dockets.pdf_title#">
                <i class="fas fa-file-pdf"></i>
            </a>
        <cfelseif dockets.isDoc EQ 1 AND len(dockets.event_url)>
            <button
                class="btn btn-sm btn-outline-primary get-pacer-pdf"
                data-doc-id="#dockets.id#"
                data-event-url="#dockets.event_url#"
                data-case-id="#dockets.fk_cases#"
                title="Download: #dockets.pdf_title#">
                <i class="fas fa-download"></i>
            </button>
        </cfif>

        <!--- Attachment PDF icons (e.g., Exhibits) --->
        <cfif len(dockets.attachment_links)>
            #dockets.attachment_links#
        </cfif>
    </div>
</td>


                            </tr>
                        </cfloop>
                    </tbody>
                </table>

                <Cfelse>
        <p>No dockets associated to this case.</p>
        </cfif>
            </div>
           

          
            <!--- Hearings Tab --->
<div class="tab-pane p-3  #hearings_tab_status#" id="hearings" role="tabpanel">
              <cfif hearings.recordcount GT 0>
                <table id="hearingTable" class="table table-striped table-bordered mt-3">
                    <thead class="table-dark">
                        <tr>
                            <th>Date</th>
                            <th>Time</th>
                            <th>Type</th>
                            <th>Description</th>
                            <th>Department</th>
                        </tr>
                    </thead>
                    <tbody>
                        <cfloop query="hearings">
                            <tr>
                                <td>#dateFormat(date, "mm/dd/yyyy")#</td>
                                <td>#timeFormat(time, "h:mm tt")#</td>
                                <td>#type#</td>
                                <td>#description#</td>
                                <td>#department#</td>
                    
                            </tr>
                        </cfloop>
                    </tbody>
                </table>
                  <Cfelse>
        <p>No hearings associated to this case.</p>
        </cfif>
            </div>
   

  
            <!--- Log Tab --->
  <div class="tab-pane p-3  #log_tab_status#" id="log" role="tabpanel">       
                 <cfif logs.recordcount GT 0>
                <table id="logTable" class="table table-striped table-bordered mt-3">
                    <thead class="table-dark">
                        <tr>
                            <th style="white-space: nowrap;">Completed</th>
                            <th style="white-space: nowrap;">Task</th>
                            <th style="white-space: nowrap;">Status</th>
                             <th style="white-space: nowrap;">Duration (MM:SS)</th>
                            <th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        <cfloop query="logs">
                            <tr>
                                <td>#dateFormat(timestamp_ended, "mm/dd/yyyy")# #timeFormat(timestamp_ended, "hh:mm tt")#</td>
                                <td>#task_name#</td>
                                <td>#status#</td>
                                <td>#duration_mmss#</td>
                                <td>#HTMLEditFormat(summary)#</td>
                            </tr>
                        </cfloop>
                    </tbody>
                </table>
                <Cfelse>
                     <p>No logs associated to this case.</p>
        </cfif>
            </div>

        <div class="tab-pane p-3 #subscribers_tab_status#" id="alerts" role="tabpanel">

        <div class="mb-3 d-flex align-items-center">
    <label for="addUserSelect" class="form-label me-2 mb-0"><strong>Add User:</strong></label>
    <select id="addUserSelect" class="form-select me-2" style="width: auto;">
    <option value=""></option>
        <cfloop query="eligible_users">
            <option value="#id#">#display#</option>
        </cfloop>
    </select>

    <button class="btn btn-primary" id="addSubscriberBtn">Add</button>
</div>

    <cfif subscribers.recordcount GT 0>
        <table id="alertsTable" class="table table-striped table-bordered mt-3">
            <thead class="table-dark">
                <tr>
                    <th>Full Name</th>
                    <th>Email</th>
                    <th>User Role</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <cfloop query="subscribers">
                <tr id="subscriberRow_#subscribers.id#">
                        <td>#fullname#</td>
                        <td>#email#</td>
                        <td>#userRole#</td>
                        <td>
    <button class="btn btn-sm btn-outline-danger" onclick="removeSubscriber(#id#)">
        <i class="fa-solid fa-trash"></i>
    </button>
</td>
                    </tr>
                </cfloop>
            </tbody>
        </table>
    <cfelse>
        <p>No subscribers for this case.</p>
    </cfif>
</div>


   <div class="tab-pane p-3  #celebrities_tab_status#" style="min-height: 300px;" id="celebrities" role="tabpanel"></cfoutput>

 





<select id="celebritySearch"></select>
<input type="hidden" id="celebrityId">
<button id="submitCelebrityBtn" class="btn btn-sm btn-primary mt-2" style="display: none;">Select Celebrity</button>

<div id="celebrityWarnings" class="mt-2" style="display: none;">
  <div id="primaryNotice" class="alert alert-info" style="display: none;"></div>
  <div id="verifyWarning" class="alert alert-warning" style="display: none;"></div>
</div>


  <input type="hidden" id="celebrityId" name="celebrityId">
  <span id="celebrityNameBadge" class="badge badge-info">No celebrity selected</span>


  <!--- Always render the table but hide it if there are no records --->
  <div id="celebrityTableWrapper" <cfif celebrities.recordcount EQ 0>style="display:none;"</cfif>>
    <table id="celebTable" class="table table-striped table-bordered mt-3">
      <thead class="table-dark">
        <tr>
          <th>Celebrity</th>
          <th>Match Status</th>
          <th>Probability</th>
          <th>Priority</th>
          <th>Ranking</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <cfloop query="celebrities">
        <cfoutput>
          <tr>
            <td>
              #celebrity_name#
              <a href="celebrity_details.cfm?id=#celebrities.celebrity_id#" target="_blank" class="text-decoration-none">
                <i class="fa-solid fa-up-right-from-square ms-1"></i>
              </a>
            </td>
            <td>#Match_status#</td>
            <td>#numberFormat(probability_score, "0.00")#</td>
            <td>#numberFormat(priority_score, "0.00")#</td>
            <td>#numberFormat(ranking_score, "0.00")#</td>
            <td>
              <button class="btn btn-sm btn-outline-danger" title="Delete" onclick="deleteCelebrityMatch('#celebrities.id#')">
                <i class="fa-solid fa-trash"></i>
              </button>
            </td>
          </tr>
          </cfoutput>
        </cfloop>
      </tbody>
    </table>
  </div>


</div>

</div>

<script>
$(document).ready(function() {
    // Attach a click handler to all buttons with the 'get-pacer-pdf' class
    $('body').on('click', '.get-pacer-pdf', function() {
        var button = $(this);
        var docId = button.data('doc-id');
        var eventUrl = button.data('event-url');
        var caseId = button.data('case-id');
        var buttonContainer = $('#button-container-' + docId);

        // Disable button and show a loading state
        button.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Getting...');

        // Make the AJAX call to your ColdFusion handler
        $.ajax({
            url: 'ajax_getPacerDoc.cfm', // The CF page that calls the Python script
            method: 'POST',
            data: {
                docID: docId,
                eventURL: eventUrl,
                caseID: caseId
            },
            dataType: 'json',
            success: function(response) {
                if (response.STATUS === 'SUCCESS') {
                    // On success, replace the button with a "View PDF" link
                    var newButton = '<a href="' + response.FILEPATH + '" target="_blank" class="btn btn-sm btn-success">View PDF</a>';
                    buttonContainer.html(newButton);
                } else {
                    // On failure, show an alert and reset the button
                    alert('Error: ' + response.MESSAGE);
                    button.prop('disabled', false).text('Get PDF');
                }
            },
            error: function(xhr, status, error) {
                // Handle server errors
                alert('An unexpected server error occurred. Please try again.');
                button.prop('disabled', false).text('Get PDF');
                console.error("AJAX Error:", status, error);
            }
        });
    });
});
</script>

<script>
function deleteCelebrityMatch(matchId) {
  Swal.fire({
    title: 'Are you sure?',
    text: 'This will remove the celebrity match from view (soft delete).',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Yes, delete it',
    cancelButtonText: 'Cancel',
    confirmButtonColor: '#d33',
    cancelButtonColor: '#aaa'
  }).then((result) => {
    if (result.isConfirmed) {
      fetch('delete_case_celebrity.cfm?bypass=1', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ id: matchId })
      })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          Swal.fire('Deleted!', data.message || 'Celebrity match removed.', 'success')
            .then(() => {
              // Reload page and activate the Celebrities tab
              const caseId = new URLSearchParams(window.location.search).get("id");
              window.location.href = `${window.location.pathname}?id=${caseId}&tab=celebrities`;
            });
        } else {
          Swal.fire('Error', data.message || 'Could not delete match.', 'error');
        }
      })
      .catch(err => Swal.fire('Error', err.message, 'error'));
    }
  });
}
</script>



            




        </div> <!--- /.tab-content --->

    </div>
</div>
 

<cfinclude template="footer_script.cfm"> <!--- Includes JS libraries --->


<script>
function updateCaseStatus(caseId, newStatus) {
    Swal.fire({
        title: 'Are you sure?',
        text: 'Set this case status to ' + newStatus + '?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#aaa',
        confirmButtonText: 'Yes, set it!'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('update_case_status.cfm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({id: caseId, status: newStatus})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        title: 'Updated!',
                        text: 'Status updated successfully.',
                        icon: 'success'
                    }).then(() => {
                        location.reload();
                    });
                } else {
                    Swal.fire('Error', 'Error updating status: ' + data.message, 'error');
                }
            })
            .catch(error => Swal.fire('Error', 'An error occurred: ' + error, 'error'));
        }
    });
}

</script>

<script>
function getUrlParam(key) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(key);
}

    $(document).ready(function () {
        // Initialize Hearings DataTable
        $('#hearingTable').DataTable({
            order: [[0, 'desc']],
            pageLength: 10
        });


        $('#docketTable').DataTable({
                 order: [[1, 'desc']],
            "paging": false,           // Disable pagination

            "info": false,             // Hide "Showing X of Y entries"
            "lengthChange": false,     // Hide "Show entries" dropdown
            "searching": true,         // Optional: keep search bar
            "ordering": true           // Optional: allow column sorting
        });
 





        // Initialize Logs DataTable
        $('#logTable').DataTable({
            order: [[0, 'desc']],
            pageLength: 25
        });

        // Make the showAddLinkModal function globally accessible
        window.showAddLinkModal = function () {
            $('#addLinkModal').modal('show');
        };

        // Handle form submission for adding a new link
        document.getElementById("addLinkForm").addEventListener("submit", function (e) {
            e.preventDefault();

            fetch("insert_case_link.cfm?bypass=1", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    fk_case: this.fk_case.value,
                    fk_user: this.fk_user.value,
                    case_url: this.case_url.value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                   Swal.fire("Success", "Link added!", "success").then(() => {
    window.location.href = window.location.pathname + "?id=" + encodeURIComponent(getUrlParam("id")) + "&tab=links";
});
                } else {
                    Swal.fire("Error", data.message || "Something went wrong", "error");
                }
            })
            .catch(err => Swal.fire("Error", err.message, "error"));
        });
    });
</script>

<script>
function deleteLink(linkId) {
    Swal.fire({
        title: 'Are you sure?',
        text: 'This will remove the link from view (soft delete).',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, delete it',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#d33',
        cancelButtonColor: '#aaa'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('delete_case_link.cfm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ id: linkId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('Deleted!', data.message || 'Link removed.', 'success')
                        .then(() => location.reload());
                } else {
                    Swal.fire('Error', data.message || 'Could not delete link.', 'error');
                }
            })
            .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
}
</script>

</body>
</html>




<!--- Add Link Modal --->
<div class="modal " id="addLinkModal" tabindex="-1" aria-labelledby="addLinkModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <form id="addLinkForm">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="addLinkModalLabel">Add New Link</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <input type="hidden" name="fk_case" value="<cfoutput>#case_details.id#</cfoutput>">
          <input type="hidden" name="fk_user" value="<cfoutput>#fk_user#</cfoutput>">

          <div class="mb-3">
            <label for="case_url" class="form-label">URL</label>
            <input type="url" class="form-control" id="case_url" name="case_url" required>
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" class="btn btn-primary">Add Link</button>
        </div>
      </div>
    </form>
  </div>
</div>

<script>
$(document).ready(function () {
  const caseId = <cfoutput>#case_details.id#</cfoutput>;

  // Init Select2 inline
  $('#celebritySearch').select2({
  placeholder: 'Lookup a celebrity to add...',
  allowClear: true,
  width: '50%',
  minimumInputLength: 0,
  ajax: {
    url: 'lookup_celebrity_autocomplete.cfm',
    dataType: 'json',
    delay: 250,
    data: function (params) {
      return { term: params.term };
    },
    processResults: function (data) {
      return {
        results: data.map(function (item) {
          return {
            id: item.celebrity_id,
            text: item.display_name,
            verified: item.verified,
            celebrity_name: item.celebrity_name
          };
        })
      };
    }
  }
});

// Show dropdown on click
$('#celebritySearch').on('focus', function () {
  $(this).select2('open');
});

  // Selection handler
  $('#celebritySearch').on('select2:select', function (e) {
    const data = e.params.data;
    $('#celebrityId').val(data.id);
    $('#submitCelebrityBtn').show();
    $('#celebrityWarnings').show();

    if (data.text !== data.celebrity_name) {
      $('#primaryNotice').html(
        `You selected <strong>${data.text}</strong>. This will be linked to the public-facing name <strong>${data.celebrity_name}</strong>.`
      ).show();
    } else {
      $('#primaryNotice').hide();
    }

    if (data.verified !== 'Verified') {
      $('#verifyWarning').html(` This name has not been verified yet.`).show();
    } else {
      $('#verifyWarning').hide();
    }
  });

  // Submission handler
  $('#submitCelebrityBtn').click(function () {
    const celebId = $('#celebrityId').val();
    const selectedData = $('#celebritySearch').select2('data')[0];
    const name = selectedData ? selectedData.text : '';

    if (!celebId) return;

    $.post("insert_case_celebrity.cfm", {
      fk_case: caseId,
      fk_celebrity: celebId
    }, function (response) {
      if (response.status === "success") {
        $('#celebrityId').val('');
        $('#celebrityNameBadge').text(name);

        const newRow = `
          <tr>
            <td>
              ${response.celebrity_name}
              <a href="celebrity_details.cfm?id=${response.celebrity_id}" target="_blank" class="text-decoration-none">
                <i class="fa-solid fa-up-right-from-square ms-1"></i>
              </a>
            </td>
            <td>${response.match_status}</td>
            <td>${response.probability_score || '0.00'}</td>
            <td>${response.priority_score || '0.00'}</td>
            <td>${response.ranking_score || '0.00'}</td>
            <td>
              <button class="btn btn-sm btn-outline-danger" title="Delete" onclick="deleteCelebrityMatch('${response.match_id}')">
                <i class="fa-solid fa-trash"></i>
              </button>
            </td>
          </tr>`;

        $('#celebrityTableWrapper').show();
        $('#celebTable tbody').append(newRow);

        $('#submitCelebrityBtn').hide();
        $('#celebrityWarnings, #primaryNotice, #verifyWarning').hide();
        $('#celebritySearch').val(null).trigger('change.select2');
      } else {
        alert("Insert failed: " + (response.error || "Unknown error"));
      }
    }, "json");
  });
});
</script>


<script>
document.getElementById('addSubscriberBtn').addEventListener('click', function () {
    const caseId = <cfoutput>#case_details.id#</cfoutput>;
    const select = document.getElementById('addUserSelect');
    const username = select.value;

    if (!username) {
        Swal.fire('Error', 'Please select a user to add.', 'warning');
        return;
    }

    fetch('insert_case_subscriber.cfm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fk_case: caseId, fk_username: username })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const tableBody = document.querySelector('#alertsTable tbody');
            const row = document.createElement('tr');
            row.id = 'subscriberRow_' + data.id;

            row.innerHTML = `
                <td>${data.firstname} ${data.lastname}</td>
                <td>${data.email}</td>
                <td>${data.userRole || 'user'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeSubscriber(${data.id})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            `;

            tableBody.appendChild(row);

            // Remove from dropdown
            select.querySelector(`option[value="${username}"]`)?.remove();
            select.selectedIndex = 0;
        } else {
            Swal.fire('Error', data.message || 'Insert failed.', 'error');
        }
    })
    .catch(err => {
        console.error(err);
        Swal.fire('Error', err.message, 'error');
    });
});
function removeSubscriber(id) {
    fetch('delete_case_subscriber.cfm?id=' + id)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Remove the row from the table
                const row = document.getElementById('subscriberRow_' + id);
                if (row) {
                    // Get name and username before removing
                    const fullName = row.querySelector('td:nth-child(1)').textContent.trim();
                    const username = data.fk_username;
                    row.remove();

                    // Add user back to dropdown
                    const select = document.getElementById('addUserSelect');
                    const option = document.createElement('option');
                    option.value = username;
                    option.textContent = fullName;
                    select.appendChild(option);
                }
            } else {
                Swal.fire('Error', data.message || 'Could not remove user.', 'error');
            }
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
}
</script>