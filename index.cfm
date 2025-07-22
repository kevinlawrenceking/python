<!--- 
================================================================================
DocketWatch - Main Cases Dashboard
================================================================================
This page provides the main interface for managing court cases within the 
DocketWatch system. It allows users to:

- View and filter cases by status (Review, Tracked, Removed)
- Search cases by various criteria (tool, owner, state, county, courthouse, celebrity)
- Perform bulk operations (track, remove, or set to review)
- Add new cases manually
- Configure column visibility
- Search document OCR content

The page uses DataTables for the main cases grid with server-side filtering
and AJAX loading for optimal performance.
================================================================================
--->

<!--- Get current authenticated user --->
<cfset currentuser = getAuthUser()>

<!--- JavaScript configuration for DataTables column definitions --->
<script>
const allColumnKeys = [
    { key: "tool_name", label: "Source" },
    { key: "case_number", label: "Case Number" },
    { key: "case_name", label: "Case Name" },
    { key: "court_name", label: "Courthouse" },
    { key: "priority", label: "Priority" },
    { key: "notes", label: "Details" },
    { key: "sortable_created_at", label: "Discovered" },
    { key: "sortable_last_updated", label: "Last Tracked" },
    { key: "possible_celebs", label: "Possible Celebs" },
    { key: "county", label: "County" },
    { key: "status", label: "Status" },
    { key: "case_url", label: "Case Link" }
];
</script>

<!--- Set case status from URL parameter --->
<cfset caseStatus = url.status ?: "Review">

<!--- Query to get user's column visibility preferences --->
<cfquery name="columnDefaults" datasource="Reach">
    SELECT column_key, is_visible
    FROM docketwatch.dbo.column_visibility_defaults
    WHERE (username = <cfqueryparam value="#currentUser#" cfsqltype="cf_sql_varchar"> OR username IS NULL)
    AND status = <cfqueryparam value="#caseStatus#" cfsqltype="cf_sql_varchar">
</cfquery>

<!--- Build visibility map for JavaScript consumption --->
<cfset visibilityMap = {}>
<cfloop query="columnDefaults">
    <cfset visibilityMap[column_key] = is_visible>
</cfloop>

<!--- URL parameter defaults --->
<cfparam name="url.status" default="Review">
<cfparam name="idlist" default="">

<!--- Query to get list of users for ownership filter --->
<cfquery name="owners" datasource="Reach">
    SELECT 
        username AS value,
        firstname + ' ' + lastname AS display
    FROM docketwatch.dbo.users
    WHERE userRole = 'User'
    ORDER BY 
        CASE WHEN username = <cfqueryparam value="#currentUser#" cfsqltype="cf_sql_varchar"> THEN 0 ELSE 1 END,
        firstname, lastname
</cfquery>

<!--- Query to get celebrities that have case matches --->
<cfquery name="celebrities" datasource="Reach">
    SELECT DISTINCT ce.id, ce.name as celebrity_name
    FROM docketwatch.dbo.celebrities ce
    WHERE ce.id IN (
        SELECT DISTINCT cm.fk_celebrity
        FROM docketwatch.dbo.case_celebrity_matches cm
        WHERE cm.match_status <> 'Removed'
    )
    ORDER BY ce.name
</cfquery>

<!--- Query to get tools that have associated cases --->
<cfquery name="tools" datasource="Reach">
    SELECT id, tool_name
    FROM docketwatch.dbo.tools
    WHERE id IN (
        SELECT DISTINCT fk_tool 
        FROM docketwatch.dbo.cases 
        WHERE fk_tool IS NOT NULL
    )
    ORDER BY tool_name
</cfquery>

<!--- Query to get all states --->
<cfquery name="states" datasource="Reach">
    SELECT state_code, state_name
    FROM docketwatch.dbo.states
    ORDER BY state_name
</cfquery>

<!--- Query to get courts with associated county and state information --->
<cfquery name="courts" datasource="Reach">
    SELECT c.court_code, c.court_name, c.fk_county, o.state_code
    FROM docketwatch.dbo.courts c
    INNER JOIN docketwatch.dbo.counties o ON o.id = c.fk_county
    ORDER BY c.court_name
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><cfoutput>#application.siteTitle#</cfoutput></title>
    <cfinclude template="head.cfm">
</head>
<body>

<cfinclude template="navbar.cfm">

<div class="container mt-4">
    <!--- Page header with title and status filter --->
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="mb-0 page-title">Cases</h2>
        <select id="statusFilter" class="form-select form-select-sm w-auto">
            <option value="Review" <cfif url.status EQ "Review">selected</cfif>>For Review</option>
            <option value="Tracked" <cfif url.status EQ "Tracked">selected</cfif>>Tracked</option>
            <option value="Removed" <cfif url.status EQ "Removed">selected</cfif>>Removed</option>
        </select>
    </div>

    <!--- Filter Panel --->
    <div class="card mb-3">
        <div class="card-body">
            <div class="row g-3 align-items-end">
                
                <!--- Owner Filter --->
                <div class="col-auto">
                    <select id="ownerFilter" class="form-select form-select-sm">
                        <option value="">All</option>
                        <cfoutput query="owners">
                            <option value="#value#" <cfif value EQ currentUser>selected</cfif>>#display#</option>
                        </cfoutput>
                    </select>
                </div>

                <!--- Tool Filter --->
                <div class="col-auto">
                    <select id="toolFilter" name="toolFilter" class="form-select form-select-sm case-filter">
                        <option value="">All Tools</option>
                    </select>
                </div>

                <!--- State Filter --->
                <div class="col-auto">
                    <select id="stateFilter" name="stateFilter" class="form-select form-select-sm case-filter">
                        <option value="">All States</option>
                    </select>
                </div>

                <!--- County Filter --->
                <div class="col-auto">
                    <select id="county_id" name="county_id" class="form-select form-select-sm case-filter">
                        <option value="">All Counties</option>
                    </select>
                </div>

                <!--- Courthouse Filter --->
                <div class="col-auto">
                    <select id="courthouseFilter" name="courthouseFilter" class="form-select form-select-sm case-filter">
                        <option value="">All Courthouses</option>
                    </select>
                </div>

                <!--- Celebrity Filter --->
                <div class="col-auto">
                    <select id="celebrityFilter" name="celebrityFilter" class="form-select form-select-sm case-filter">
                        <option value="">All Celebrities</option>
                    </select>
                </div>

            </div>
        </div>
    </div>

    <!--- Document OCR Search Panel --->
    <div class="card mb-3">
        <div class="card-body">
            <div class="row">
                <div class="col">
                    <input type="text" class="form-control" id="documentSearch" placeholder="Search document OCR text..." autocomplete="off">
                </div>
            </div>
        </div>
    </div>

    <!--- Action Panel --->
    <div class="card mb-3">
        <div class="card-body">
            <cfoutput>
                <button id="removeCases" class="btn btn-danger">Remove Cases</button>
                <button id="trackCases" class="btn btn-primary">Track Cases</button>
                <button id="ReviewCases" class="btn btn-primary">Set to Review</button>
                <a href="add_blank_case.cfm"><button id="AddCase" class="btn btn-primary">Track a New Case</button></a>
                <button class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="##columnVisibilityModal">Column Options</button>
                <button id="refreshFilters" class="btn btn-secondary">Refresh</button>
            </cfoutput>
        </div>
    </div>


    <!--- Main Cases DataTable --->
    <table id="casesTable" class="table w-100 table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <th><input type="checkbox" id="select-all"></th>
                <th>Sources</th>
                <th style="display:none;">ID</th> <!--- Hidden ID column for internal use --->
                <th>Case Number</th>
                <th>Case Name</th>
                <th>Courthouse</th>
                <th>Priority</th>
                <th>Details</th>
                <th>Discovered</th>
                <th>Last Tracked</th>
                <th nowrap>Possible Celebs</th>
                <th>County</th>
                <th>Status</th>
                <th>Link</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

<cfinclude template="footer_script.cfm">

<!--- User Activity Logging (only log once per session) --->
<cfif NOT isDefined("session.userActivityLogged") OR session.userActivityLogged NEQ true>
    <cftry>
        <cfset login_name = getAuthUser()>
        <cfif NOT isDefined("login_name") OR len(trim(login_name)) EQ 0>
            <cfset login_name = "user">
        </cfif>
        
        <cfquery datasource="reach">
            INSERT INTO docketwatch.dbo.UserActivity (UserName, PageName, CGI_IP, CGI_UserAgent)
            VALUES (
                <cfqueryparam value="#login_name#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#CGI.SCRIPT_NAME#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#CGI.IP_ADDRESS#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#CGI.HTTP_USER_AGENT#" cfsqltype="cf_sql_varchar">
            );
        </cfquery>
        <cfset session.userActivityLogged = true>
        <cfcatch type="any">
            <!--- Log error silently without affecting page load --->
        </cfcatch>
    </cftry>
</cfif>

<!--- Column Visibility Modal --->
<div class="modal fade" id="columnVisibilityModal" tabindex="-1" aria-labelledby="columnVisibilityLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Customize Column Visibility</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <select id="statusSelector" class="form-select mb-3">
                    <option value="Review">Review</option>
                    <option value="Tracked">Tracked</option>
                </select>
                <div id="columnOptionsContainer" class="row g-2">
                    <!--- Checkboxes populated dynamically by JavaScript --->
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button class="btn btn-primary" onclick="saveColumnVisibility()">Save</button>
            </div>
        </div>
    </div>
</div>

<!--- Track New Case Modal --->
<div class="modal fade" id="trackCaseModal" tabindex="-1" aria-labelledby="trackCaseModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="trackCaseModalLabel">Track New Case</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <form id="trackCaseForm">
                    <cfoutput>
                        <input type="hidden" id="currentuser" name="currentuser" value="#currentuser#">
                    </cfoutput>
                    
                    <div class="mb-3">
                        <label for="toolSelect" class="form-label">Tool <span class="text-danger">*</span></label>
                        <select class="form-select" id="toolSelect" required onchange="updateFieldRequirements()">
                            <option value="">Select Tool</option>
                            <cfquery name="getUserTools" datasource="Reach">
                                SELECT id as fk_tool, tool_name
                                FROM docketwatch.dbo.tools
                                WHERE owners LIKE <cfqueryparam value="%#currentUser#%" cfsqltype="cf_sql_varchar">
                                AND addNew = 1
                                ORDER BY tool_name
                            </cfquery>
                            <cfoutput query="getUserTools">
                                <option value="#fk_tool#">#tool_name#</option>
                            </cfoutput>
                        </select>
                    </div>

                    <!--- Case URL Field (shown for specific tools) --->
                    <div class="mb-3" id="caseUrlGroup" style="display: none;">
                        <label for="caseUrl" class="form-label">Case URL <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" id="caseUrl">
                    </div>

                    <!--- Case Number Field (shown for specific tools) --->
                    <div class="mb-3" id="caseNumberGroup" style="display: none;">
                        <label for="caseNumber" class="form-label">Case Number <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" id="caseNumber">
                    </div>

                    <!--- Case Name Field (optional) --->
                    <div class="mb-3" id="caseNameGroup" style="display: none;">
                        <label for="caseName" class="form-label">Case Name</label>
                        <input type="text" class="form-control" id="caseName">
                    </div>

                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="submitNewCase()">Submit</button>
            </div>
        </div>
    </div>
</div>


 
<script>
/**
 * Configuration and Utility Functions
 * ==================================
 */

// Column visibility defaults from server-side ColdFusion
const columnVisibilityDefaults = <cfoutput>#serializeJSON(visibilityMap)#</cfoutput>;

// Utility function for debouncing user input to prevent excessive API calls
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Centralized localStorage management for filter persistence
const LocalStorageManager = {
    keys: {
        tool: 'selectedTool',
        owner: 'docketwatch_owner',
        courthouse: 'selectedCourthouse',
        county: 'selectedCounty',
        state: 'selectedState',
        celebrity: 'selectedCelebrity'
    },
    
    set(key, value) {
        if (this.keys[key]) {
            localStorage.setItem(this.keys[key], value);
        }
    },
    
    get(key) {
        return this.keys[key] ? localStorage.getItem(this.keys[key]) : null;
    },
    
    clearAll() {
        Object.values(this.keys).forEach(key => localStorage.removeItem(key));
    }
};
</script>


<script>
function reloadDropdownsAsync() {
    var filters = {
        status: $('#statusFilter').val(),
        tool: $('#toolFilter').val(),
        owner: $('#ownerFilter').val(),
        state: $('#stateFilter').val(),
        county: $('#county_id').val(),
        courthouse: $('#courthouseFilter').val(),
        fk_celebrity: $('#celebrityFilter').val()
    };

    const loaders = [
        { url: 'get_tools.cfm', target: '#toolFilter', selected: LocalStorageManager.get('tool') },
        { url: 'get_states.cfm', target: '#stateFilter', selected: LocalStorageManager.get('state') },
        { url: 'get_counties.cfm', target: '#county_id', selected: LocalStorageManager.get('county') },
        { url: 'get_courthouses.cfm', target: '#courthouseFilter', selected: LocalStorageManager.get('courthouse') },
        { url: 'get_celebrities.cfm', target: '#celebrityFilter', selected: LocalStorageManager.get('celebrity') }
    ];

    return Promise.all(loaders.map(item =>
        new Promise(resolve => {
            $.get(item.url, filters, function(data) {
                $(item.target).html(data);
                if (item.selected && $(item.target + ' option[value="' + item.selected + '"]').length) {
                    $(item.target).val(item.selected);
                }
                resolve();
            });
        })
    ));
}

// Column rendering utilities
const ColumnRenderers = {
    defaultOrFallback: (data, fallback = "(None)") => data || fallback,
    
    caseNumber: function(data, type, row) {
        let html = `<a href="${row.internal_case_url}" title="View in DocketWatch" class="text-muted me-2">
                    <i class="fa-solid fa-file-lines"></i></a>`;
        
        if (row.external_case_url) {
            html += `<a href="${row.external_case_url}" target="_blank" title="Open Official Court Page" class="text-muted"><i class="fa-solid fa-up-right-from-square"></i></a>`;
        }
        
        if (row.pdf_link && row.pdf_link.trim() !== "") {
            html += `<a href="${row.pdf_link}" target="_blank" title="View PDF" class="text-danger ms-2"><i class="fa-solid fa-file-pdf"></i></a>`;
        }
        
        return data + ' ' + html;
    },
    dateFormat: function(data, type, row, formattedField) {
        return type === 'display' ? (row[formattedField] || "(No Date)") : data;
    },
    
    lastUpdated: function(data, type, row) {
        if (type === 'display') {
            let text = row.formatted_last_updated || "(No Date)";
            if (row.not_found_count && row.not_found_count > 0) {
                const plural = row.not_found_count > 1 ? 's' : '';
                return `<a href="not_found.cfm#case${row.id}" style="color: #b91c1c; font-weight: bold; text-decoration:underline;">
                        ${text} 
                        <i class="fa fa-exclamation-triangle" title="Case not found ${row.not_found_count} time${plural}"></i>
                        <span style="font-size:90%;font-weight:normal;">(${row.not_found_count})</span>
                    </a>`;
            }
            return text;
        }
        return data;
    },
    
    celebrities: (data) => data ? data.replace(/, /g, "<br>") : "(None)"
};

function initializeCasesTable() {
    window.table = $('#casesTable').DataTable({
        dom: '<"dt-toolbar d-flex justify-content-between align-items-center mb-2"lfB>rt<"bottom"ip><"clear">',
        buttons: [
            {
                extend: 'colvis',
                columns: ':not(.noVis)', // Exclude critical columns like checkboxes or IDs
                text: 'Choose Columns',
                titleAttr: 'Select visible columns'
            }
        ],
        columnDefs: [
            {
                targets: [0, 2], // Prevent visibility toggle for checkbox and ID
                className: 'noVis'
            }
        ],
        ajax: {
            url: "cases_ajax.cfm",
            data: function (d) {
                d.status     = $('#statusFilter').val();
                d.county     = $('#county_id').val();
                d.tool       = $('#toolFilter').val();
                d.owner      = $('#ownerFilter').val();
                d.state      = $('#stateFilter').val();
                d.courthouse = $('#courthouseFilter').val();
                d.celebrity  = $('#celebrityFilter').val();
                d.docsearch  = $('#documentSearch').val();
            },
            dataSrc: function (json) {
                console.log("AJAX Response Data:", json);
                return Array.isArray(json) ? json : [];
            },
            error: function (xhr, error, thrown) {
                console.error("AJAX Error:", error, thrown);
            }
        },
columns: [
    {
        data: null,
        orderable: false,
        className: "select-checkbox noVis",
        render: function (data, type, row) {
            return '<input type="checkbox" class="row-checkbox" value="' + row.id + '">';
        }
    },
    { data: "tool_name", visible: columnVisibilityDefaults["tool_name"] === 1, title: "Source", defaultContent: "(None)" },
    { data: "id", visible: false, className: "noVis" },
    {
        data: "case_number",
        className: "nowrap",
        visible: columnVisibilityDefaults["case_number"] === 1,
        render: ColumnRenderers.caseNumber
    },
    {
        data: "case_name",
        visible: columnVisibilityDefaults["case_name"] === 1,
        defaultContent: "(None)",
        render: function(data) { return ColumnRenderers.defaultOrFallback(data); }
    },
    { data: "court_name", visible: columnVisibilityDefaults["court_name"] === 1, defaultContent: "(Unknown)" },
    { data: "priority", visible: columnVisibilityDefaults["priority"] === 1, defaultContent: "(None)" },
    {
        data: "notes",
        visible: columnVisibilityDefaults["notes"] === 1,
        defaultContent: "(No Details)",
        render: function(data) { return ColumnRenderers.defaultOrFallback(data, "(No Details)"); }
    },
    {
        data: "sortable_created_at",
        visible: columnVisibilityDefaults["sortable_created_at"] === 1,
        className: "nowrap",
        render: function(data, type, row) { return ColumnRenderers.dateFormat(data, type, row, 'formatted_created_at'); }
    },
    {
        data: "sortable_last_updated",
        visible: columnVisibilityDefaults["sortable_last_updated"] === 1,
        className: "nowrap",
        render: ColumnRenderers.lastUpdated
    },
    {
        data: "possible_celebs",
        visible: columnVisibilityDefaults["possible_celebs"] === 1,
        defaultContent: "(None)",
        render: function(data) { return ColumnRenderers.celebrities(data); }
    },
    { data: "county", visible: columnVisibilityDefaults["county"] === 1, defaultContent: "(None)" },
    { data: "status", visible: columnVisibilityDefaults["status"] === 1, defaultContent: "(None)" },
    { data: "case_url", visible: columnVisibilityDefaults["case_url"] === 1, defaultContent: "(None)" }
],

        paging: true,
        searching: true,
        ordering: true,
        info: true,
        order: [[8, "desc"]],
        pageLength: 10,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        processing: true,
        serverSide: false
    });
}


/**
 * Main Application Initialization
 * ===============================
 */
$(document).ready(function () {
    // Initialize page: Load all dropdown filters and set up table
    reloadDropdownsAsync().then(function() {
        // Initialize DataTable after filters are loaded
        initializeCasesTable();

        // Setup unified filter change handlers for all dropdowns
        $('#toolFilter, #county_id, #courthouseFilter, #celebrityFilter, #ownerFilter, #stateFilter, #statusFilter').on('change', function () {
            const id = $(this).attr('id');
            const val = $(this).val();
            
            // Map filter IDs to localStorage keys
            const storageMap = {
                'toolFilter': 'tool',
                'ownerFilter': 'owner',
                'courthouseFilter': 'courthouse',
                'county_id': 'county',
                'stateFilter': 'state',
                'celebrityFilter': 'celebrity'
            };
            
            // Save filter state to localStorage
            if (storageMap[id]) {
                LocalStorageManager.set(storageMap[id], val);
            }

            // Reload dependent dropdowns and refresh table
            reloadDropdownsAsync().then(function() {
                $('#casesTable').DataTable().ajax.reload();
            });

            // Update page title based on status filter
            if (id === 'statusFilter') {
                const statusText = {
                    "Review": "New Cases Review",
                    "Tracked": "Tracked Cases",
                    "Removed": "Removed Cases"
                }[val] || "Cases";
                $('.page-title').text(statusText);
            }
        });

        // Setup document search with debouncing
        $('#documentSearch').on('input', debounce(function() {
            $('#casesTable').DataTable().ajax.reload();
        }, 300));

        // Configure action button visibility based on status and selection
        const actionButtons = {
            '#removeCases': { hideOnLoad: true, showWhen: (status, hasChecked) => status === 'Review' && hasChecked },
            '#trackCases': { hideOnLoad: true, showWhen: (status, hasChecked) => status === 'Review' && hasChecked },
            '#trackCaseModalBtn': { hideOnLoad: true, showWhen: (status, hasChecked) => status === 'Review' && hasChecked },
            '#ReviewCases': { hideOnLoad: true, showWhen: (status, hasChecked) => status === 'Tracked' && hasChecked },
            '#trackAdd': { hideOnLoad: true, showWhen: (status, hasChecked) => status === 'Tracked' },
            '#refreshFilters': { hideOnLoad: true, showWhen: (status, hasChecked, hasFilters) => hasFilters }
        };

        // Hide action buttons initially
        Object.keys(actionButtons).forEach(selector => {
            if (actionButtons[selector].hideOnLoad) {
                $(selector).hide();
            }
        });

        // Function to update action button visibility
        function updateActionButtons() {
            const status = $('#statusFilter').val();
            const anyChecked = $('.row-checkbox:checked').length > 0;
            const filters = ['#toolFilter','#ownerFilter','#stateFilter','#county_id','#courthouseFilter','#celebrityFilter'];
            const anyFilterSet = filters.some(sel => $(sel).val()?.length > 0);
            
            Object.entries(actionButtons).forEach(([selector, config]) => {
                const shouldShow = config.showWhen(status, anyChecked, anyFilterSet);
                $(selector).toggle(shouldShow);
            });
        }

        // Bind action button update events
        $(document).on('change', '.row-checkbox', updateActionButtons);
        $('#statusFilter, #toolFilter, #ownerFilter, #stateFilter, #county_id, #courthouseFilter, #celebrityFilter')
            .on('change', updateActionButtons);
        $('#casesTable').on('draw.dt', updateActionButtons);

        // Setup select-all checkbox functionality
        $('#select-all').on('click', function() {
            var isChecked = this.checked;
            $('.row-checkbox').prop('checked', isChecked).trigger('change');
        });

        // Allow clicking on checkbox cell to toggle checkbox
        $('#casesTable tbody').on('click', 'td.select-checkbox', function(event) {
            if (!$(event.target).is('input')) {
                var checkbox = $(this).find('input.row-checkbox');
                checkbox.prop('checked', !checkbox.prop('checked')).trigger('change');
            }
        });

        // Setup refresh button to clear all filters
        $('#refreshFilters').on('click', function () {
            LocalStorageManager.clearAll();
            $('#statusFilter').val('Review');
            $('#toolFilter, #ownerFilter, #stateFilter, #county_id, #courthouseFilter, #celebrityFilter').val('');
            reloadDropdownsAsync().then(function() {
                $('#casesTable').DataTable().ajax.reload();
            });
            $('.page-title').text('New Cases Review');
        });
    });
});

/**
 * Case Status Management Functions
 * ===============================
 */

// Generic function to update case status with confirmation
function updateCaseStatus(caseId, newStatus) {
    Swal.fire({
        title: 'Are you sure?',
        text: 'Set selected cases to ' + newStatus + '?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#aaa',
        confirmButtonText: 'Yes, set it!'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('update_case_status_list.cfm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idlist: caseId, status: newStatus })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        title: 'Updated!',
                        text: 'Status updated successfully.',
                        icon: 'success'
                    }).then(() => {
                        table.ajax.reload(null, false);
                        $('.row-checkbox').prop('checked', false);
                        updateActionButtons();
                    });
                } else {
                    Swal.fire('Error', 'Error updating status: ' + data.message, 'error');
                }
            })
            .catch(error => Swal.fire('Error', 'An error occurred: ' + error, 'error'));
        }
    });
}

// Button event handlers for case status changes
$('#removeCases').on('click', function () {
    const selected = getSelectedCaseIds();
    if (selected.length === 0) return alert("No cases selected.");
    updateCaseStatus(selected.join(','), 'Removed');
});

$('#trackCases').on('click', function () {
    const selected = getSelectedCaseIds();
    if (selected.length === 0) return alert("No cases selected.");
    updateCaseStatus(selected.join(','), 'Tracked');
});

$('#ReviewCases').on('click', function () {
    const selected = getSelectedCaseIds();
    if (selected.length === 0) return alert("No cases selected.");
    updateCaseStatus(selected.join(','), 'Review');
});

// Utility function to get selected case IDs
function getSelectedCaseIds() {
    const ids = [];
    $('.row-checkbox:checked').each(function () {
        ids.push($(this).val());
    });
    return ids;
}

/**
 * New Case Modal Functions
 * =======================
 */

// Update form field requirements based on selected tool
function updateFieldRequirements() {
    const tool = document.getElementById('toolSelect').value;
    const caseUrlGroup = document.getElementById('caseUrlGroup');
    const caseNumberGroup = document.getElementById('caseNumberGroup');
    const caseNameGroup = document.getElementById('caseNameGroup');
    const caseUrl = document.getElementById('caseUrl');
    const caseNumber = document.getElementById('caseNumber');
    const caseName = document.getElementById('caseName');

    // Hide all fields by default
    caseUrlGroup.style.display = 'none';
    caseNumberGroup.style.display = 'none';
    caseNameGroup.style.display = 'none';
    caseUrl.required = false;
    caseNumber.required = false;

    // Show relevant fields based on tool selection
    if (tool === "2") { // UniCourt
        caseUrlGroup.style.display = 'block';
        caseUrl.required = true;
    } else if (tool === "13" || tool === "25") { // PACER, Broward, etc.
        caseNumberGroup.style.display = 'block';
        caseNumber.required = true;
    }
}

// Initialize field requirements when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    const toolSelect = document.getElementById('toolSelect');
    if (toolSelect) {
        toolSelect.addEventListener('change', updateFieldRequirements);
        updateFieldRequirements(); // Run on load in case tool is preselected
    }
});

// Submit new case form
function submitNewCase() {
    const tool = document.getElementById('toolSelect').value;
    const caseUrlEl = document.getElementById('caseUrl');
    const caseNumberEl = document.getElementById('caseNumber');
    const caseNameEl = document.getElementById('caseName');
    const currentuser = document.getElementById('currentuser').value.trim();

    // Only collect values from visible fields
    const caseUrl = caseUrlEl.offsetParent !== null ? caseUrlEl.value.trim() : '';
    const caseNumber = caseNumberEl.offsetParent !== null ? caseNumberEl.value.trim() : '';
    const caseName = caseNameEl.offsetParent !== null ? caseNameEl.value.trim() : '';

    if (!tool) {
        Swal.fire('Validation Error', 'Please select a tool.', 'warning');
        return;
    }

    // Show loading indicator
    Swal.fire({
        title: 'Tracking Case...',
        html: 'Please wait while the case is processed.',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    // Submit case data
    fetch('insert_new_case.cfm?bypass=1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool, caseUrl, caseNumber, caseName, currentuser })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success && data.inserted_case_id) {
            Swal.fire('Success', 'Case added successfully.', 'success')
                .then(() => window.location.href = `case_details.cfm?id=${data.inserted_case_id}`);
        } else {
            Swal.fire('Error', data.message || 'Unknown error', 'error');
        }
    })
    .catch(err => Swal.fire('Error', err.message || err, 'error'));
}
</script>

<script>
/**
 * Column Visibility Modal Functions
 * =================================
 */
document.addEventListener('DOMContentLoaded', function () {
    // Setup column visibility modal - populate checkboxes when modal opens
    $('#columnVisibilityModal').on('show.bs.modal', function () {
        const status = $('#statusSelector').val();
        const container = $('#columnOptionsContainer');
        container.empty();

        // Create checkbox for each column
        allColumnKeys.forEach(col => {
            const checked = columnVisibilityDefaults[col.key] === 1;
            const checkbox = `
                <div class="col-md-4">
                    <div class="form-check">
                        <input class="form-check-input col-check" type="checkbox" 
                            data-col="${col.key}" id="col-${col.key}" ${checked ? 'checked' : ''}>
                        <label class="form-check-label" for="col-${col.key}">
                            ${col.label}
                        </label>
                    </div>
                </div>`;
            container.append(checkbox);
        });
    });

    // Refresh modal when status selector changes
    $('#statusSelector').on('change', function () {
        $('#columnVisibilityModal').modal('show'); // Force re-trigger modal setup
    });
});

// Save column visibility preferences
function saveColumnVisibility() {
    const status = $('#statusSelector').val();
    const updates = [];

    // Collect all checkbox states
    $('.col-check').each(function () {
        const col = $(this).data('col');
        const isVisible = $(this).is(':checked') ? 1 : 0;
        updates.push({ column_key: col, is_visible: isVisible });
    });

    // Send updates to server
    fetch('save_column_visibility.cfm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, updates })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            Swal.fire("Saved", "Column visibility saved successfully.", "success")
                .then(() => location.reload()); // Refresh page to apply changes
        } else {
            Swal.fire("Error", data.message || "Failed to save settings.", "error");
        }
    })
    .catch(err => Swal.fire("Error", err.message, "error"));
}
</script>


</body>
</html>
</html>
