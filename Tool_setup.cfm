<cfquery name="getCounties" datasource="reach">
  SELECT [id], [name] + ', ' + state_code AS display_name
  FROM [docketwatch].[dbo].[counties]
  ORDER BY name, state_code
</cfquery>

<cfquery name="getTools" datasource="reach">
  SELECT 
      [id], [tool_name], [api_base_url], [api_key], [auth_method],
      [login_url], [username], [pass], [search_url], [owners], [fk_county],
      [addNew], [isLogin],[login_checkbox],[case_name_input],
      [captcha_type], [captcha_image_selector], [captcha_input_selector], [captcha_submit_selector],
      [case_number_input], [search_button_selector], [result_row_selector], [case_link_selector],
      [case_name_selector], [court_name_selector], [case_type_selector],
      [events_table_selector], [event_col_0_label], [event_col_1_label], [event_col_2_label],
      [events_column_count], [pre_search_click_selector], [username_selector], [password_selector]
  FROM [docketwatch].[dbo].[tools]
  WHERE id = #url.id#
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Edit Tool</title>
  <cfinclude template="head.cfm">
</head>
<body>
<cfinclude template="navbar.cfm">

<div class="container mt-4">
 <div class="d-flex justify-content-between align-items-center mb-4">
  <h1><cfoutput>#getTools.tool_name# </cfoutput>: Tool Configuration</h1>
  <a href="tools.cfm" class="btn btn-primary">Back to Tools</a>
</div>


  <cfoutput>
<form method="post" action="tool_update2.cfm">
    <input type="hidden" id="tool_id" name="tool_id" value="#getTools.id#">

    <div class="mb-4">
  <h3>Basic Info</h3>

  <div class="mb-3">
    <label for="tool_name">Tool Name *</label>
    <input type="text" class="form-control" id="tool_name" name="tool_name" value="#getTools.tool_name#" required>
  </div>


 
  <div class="mb-3">
    <label for="owners">Owners (comma-separated usernames)</label>
    <input type="text" class="form-control" id="owners" name="owners" value="#htmleditformat(getTools.owners)#">
  </div>

  <div class="mb-3">
    </cfoutput>
<label for="fk_county">Associated County</label>
    <select class="form-select" id="fk_county" name="fk_county">
      <option value="">-- Select a County --</option>
      <cfoutput query="getCounties">
        <option value="#id#" <cfif id EQ getTools.fk_county>selected</cfif>>#display_name#</option>
      </cfoutput>

    </select>
  </div>

  <div class="form-check mb-3">
    <input class="form-check-input" type="checkbox" id="addNew" name="addNew" <cfif getTools.addNew EQ 1>checked</cfif>>
    <label class="form-check-label" for="addNew">Allow Add New Cases</label>
  </div>

  <div class="form-check mb-3">
<cfoutput>
<input class="form-check-input" type="checkbox" id="isLogin" name="isLogin"
  data-login="#getTools.isLogin#" <cfif getTools.isLogin EQ 1>checked</cfif>>
</cfoutput>


    <label class="form-check-label" for="isLogin">Requires Login</label>
  </div>
</div>


<cfoutput>
    <div class="mb-4" id="loginSection">
  <h3>Login Configuration</h3>

  <div class="mb-3">
    <label for="login_url">Login URL</label>
    <input type="text" class="form-control" id="login_url" name="login_url" value="#getTools.login_url#">
  </div>

  <div class="mb-3">
    <label for="username">Username</label>
    <input type="text" class="form-control" id="username" name="username" value="#getTools.username#">
  </div>

  <div class="mb-3">
    <label for="pass">Password</label>
    <input type="text" class="form-control" id="pass" name="pass" value="#getTools.pass#">
  </div>

  <div class="mb-3">
    <label for="username_selector">Username Input Selector</label>
    <input type="text" class="form-control" id="username_selector" name="username_selector" value="#htmleditformat(getTools.username_selector)#">
  </div>

  <div class="mb-3">
    <label for="password_selector">Password Input Selector</label>
    <input type="text" class="form-control" id="password_selector" name="password_selector" value="#htmleditformat(getTools.password_selector)#">
  </div>

  <div class="mb-3">
    <label for="login_checkbox">Login Checkbox Selector (optional)</label>
    <input type="text" class="form-control" id="login_checkbox" name="login_checkbox" value="#htmleditformat(getTools.login_checkbox)#">
  </div>
</div>
</cfoutput>
    <div class="mb-4">
  <h3>API Configuration</h3>
<cfoutput>
  <div class="mb-3">
    <label for="api_base_url">API Base URL</label>
    <input type="text" class="form-control" id="api_base_url" name="api_base_url" value="#getTools.api_base_url#">
  </div>

  <div class="mb-3">
    <label for="api_key">API Key</label>
    <input type="text" class="form-control" id="api_key" name="api_key" value="#getTools.api_key#">
  </div>

  <div class="mb-3">
    <label for="auth_method">Authentication Method</label>
    <input type="text" class="form-control" id="auth_method" name="auth_method" value="#getTools.auth_method#">
  </div>
</div>

    <div class="mb-4">
      <h3>Court Scraper Selectors</h3>

        <div class="mb-3">
    <label for="search_url">Enter URL to search</label>
    <input type="text" class="form-control" id="search_url" name="search_url" value="#getTools.search_url#">
  </div>



      <div class="mb-3">
        <label for="case_number_input">Add the ##ID of the Case Number Input Box</label>
        <input type="text" class="form-control" id="case_number_input" name="case_number_input" value="#htmlEditFormat(getTools.case_number_input)#">
      </div>

            <div class="mb-3">
        <label for="case_number_input">Add the ##ID of the Case Name Input Box</label>
        <input type="text" class="form-control" id="case_name_input" name="case_name_input" value="#htmlEditFormat(getTools.case_name_input)#">
      </div>

      <div class="mb-3">
        <label for="search_button_selector">Search Button Selector</label>
        <input type="text" class="form-control" id="search_button_selector" name="search_button_selector" value="#htmleditformat(getTools.search_button_selector)#">
      </div>

      <div class="mb-3">
        <label for="result_row_selector">Result Row Selector</label>
        <input type="text" class="form-control" id="result_row_selector" name="result_row_selector" value="#htmleditformat(getTools.result_row_selector)#">
      </div>

      <div class="mb-3">
        <label for="events_table_selector">Events Table Selector</label>
        <input type="text" class="form-control" id="events_table_selector" name="events_table_selector" value="#htmleditformat(getTools.events_table_selector)#">
      </div>

      <div class="mb-3">
        <label for="events_column_count">Number of Columns in Events Table</label>
        <input type="number" class="form-control" id="events_column_count" name="events_column_count" value="#getTools.events_column_count#">
      </div>

      <div class="mb-3">
        <label for="pre_search_click_selector">Pre-Search Click Selector (optional)</label>
        <input type="text" class="form-control" id="pre_search_click_selector" name="pre_search_click_selector" value="#htmleditformat(getTools.pre_search_click_selector)#">
      </div>
    </div>

    <div class="mb-4">
      <h3>CAPTCHA Configuration</h3>

      <div class="mb-3">
        <label for="captcha_type">CAPTCHA Type</label>
        <input type="text" class="form-control" id="captcha_type" name="captcha_type" value="#getTools.captcha_type#">
      </div>

      <div class="mb-3">
        <label for="captcha_image_selector">CAPTCHA Image Selector</label>
        <input type="text" class="form-control" id="captcha_image_selector" name="captcha_image_selector" value="#htmleditformat(getTools.captcha_image_selector)#">
      </div>

      <div class="mb-3">
        <label for="captcha_input_selector">CAPTCHA Input Field Selector</label>
        <input type="text" class="form-control" id="captcha_input_selector" name="captcha_input_selector" value="#htmleditformat(getTools.captcha_input_selector)#">
      </div>

      <div class="mb-3">
        <label for="captcha_submit_selector">CAPTCHA Submit Button Selector</label>
        <input type="text" class="form-control" id="captcha_submit_selector" name="captcha_submit_selector" value="#htmleditformat(getTools.captcha_submit_selector)#">
      </div>
    </div>

    <div class="mb-4">
      <h3>Optional Case Metadata</h3>

      <div class="mb-3">
        <label for="case_link_selector">Case Link Selector</label>
        <input type="text" class="form-control" id="case_link_selector" name="case_link_selector" value="#htmleditformat(getTools.case_link_selector)#">
      </div>

      <div class="mb-3">
        <label for="case_name_selector">Case Name Selector</label>
        <input type="text" class="form-control" id="case_name_selector" name="case_name_selector" value="#htmleditformat(getTools.case_name_selector)#">
      </div>

      <div class="mb-3">
        <label for="court_name_selector">Court Name Selector</label>
        <input type="text" class="form-control" id="court_name_selector" name="court_name_selector" value="#htmleditformat(getTools.court_name_selector)#">
      </div>

      <div class="mb-3">
        <label for="case_type_selector">Case Type Selector</label>
        <input type="text" class="form-control" id="case_type_selector" name="case_type_selector" value="#htmleditformat(getTools.case_type_selector)#">
      </div>

      <div class="mb-3">
        <label for="event_col_0_label">Event Column 1 Label</label>
        <input type="text" class="form-control" id="event_col_0_label" name="event_col_0_label" value="#htmleditformat(getTools.event_col_0_label)#">
      </div>

      <div class="mb-3">
        <label for="event_col_1_label">Event Column 2 Label</label>
        <input type="text" class="form-control" id="event_col_1_label" name="event_col_1_label" value="#htmleditformat(getTools.event_col_1_label)#">
      </div>

      <div class="mb-3">
        <label for="event_col_2_label">Event Column 3 Label</label>
        <input type="text" class="form-control" id="event_col_2_label" name="event_col_2_label" value="#htmleditformat(getTools.event_col_2_label)#">
      </div>
    </div>

    <button type="submit" class="btn btn-primary">Save Changes</button>
  </form>
</cfoutput>
</div>
<script>
  document.addEventListener("DOMContentLoaded", function () {
    const loginCheckbox = document.getElementById("isLogin");
    const loginSection = document.getElementById("loginSection");

    function toggleLoginSection() {
      loginSection.style.display = loginCheckbox.checked ? "block" : "none";
    }

    loginCheckbox.addEventListener("change", toggleLoginSection);
    toggleLoginSection(); // run once on page load
  });
</script>


<cfinclude template="footer_script.cfm">
</body>
</html>
