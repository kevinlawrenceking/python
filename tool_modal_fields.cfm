<cfquery name="getCounties" datasource="reach">
  SELECT [id], [name] + ', ' + state_code AS display_name
  FROM [docketwatch].[dbo].[counties]
  ORDER BY name, state_code
</cfquery>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Tool Setup</title>
  <cfinclude template="head.cfm">
</head>
<body>
<cfinclude template="navbar.cfm">

<div class="container mt-4">
  <h1 class="mb-4">Tool Setup</h1>

  <form method="post" action="save_tool.cfm">
    <input type="hidden" id="tool_id" name="tool_id">

    <!--- Basic Tool Info --->
    <div class="mb-4">
      <h3>Basic Info</h3>

      <div class="mb-3">
        <label for="tool_name">Tool Name *</label>
        <input type="text" class="form-control" id="tool_name" name="tool_name" required>
      </div>

      <div class="mb-3">
        <label for="search_url">Search Page URL</label>
        <input type="text" class="form-control" id="search_url" name="search_url">
      </div>

      <div class="mb-3">
        <label for="owners">Owners (comma-separated usernames)</label>
        <input type="text" class="form-control" id="owners" name="owners">
      </div>

      <div class="mb-3">
        <label for="fk_county">Associated County</label>
        <select class="form-select" id="fk_county" name="fk_county">
          <option value="">-- Select a County --</option>
          <cfoutput query="getCounties">
            <option value="#id#">#display_name#</option>
          </cfoutput>
        </select>
      </div>

      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="addNew" name="addNew">
        <label class="form-check-label" for="addNew">Allow Add New Cases</label>
      </div>

      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="isLogin" name="isLogin">
        <label class="form-check-label" for="isLogin">Requires Login</label>
      </div>
    </div>

    <!--- API Configuration --->
    <div class="mb-4">
      <h3>API Configuration</h3>

      <div class="mb-3">
        <label for="api_base_url">API Base URL</label>
        <input type="text" class="form-control" id="api_base_url" name="api_base_url">
      </div>

      <div class="mb-3">
        <label for="api_key">API Key</label>
        <input type="text" class="form-control" id="api_key" name="api_key">
      </div>

      <div class="mb-3">
        <label for="auth_method">Authentication Method</label>
        <input type="text" class="form-control" id="auth_method" name="auth_method">
      </div>
    </div>

    <!--- Login Configuration --->
    <div class="mb-4" id="loginSection" style="display:none;">
      <h3>Login Configuration</h3>

      <div class="mb-3">
        <label for="login_url">Login URL</label>
        <input type="text" class="form-control" id="login_url" name="login_url">
      </div>

      <div class="mb-3">
        <label for="username">Username</label>
        <input type="text" class="form-control" id="username" name="username">
      </div>

      <div class="mb-3">
        <label for="pass">Password</label>
        <input type="text" class="form-control" id="pass" name="pass">
      </div>

      <div class="mb-3">
        <label for="username_selector">Username Input Selector</label>
        <input type="text" class="form-control" id="username_selector" name="username_selector">
      </div>

      <div class="mb-3">
        <label for="password_selector">Password Input Selector</label>
        <input type="text" class="form-control" id="password_selector" name="password_selector">
      </div>

      <div class="mb-3">
        <label for="login_checkbox">Login Checkbox Selector (optional)</label>
        <input type="text" class="form-control" id="login_checkbox" name="login_checkbox">
      </div>
    </div>

    <!--- Scraper Selectors --->
    <div class="mb-4">
      <h3>Court Scraper Selectors</h3>

      <div class="mb-3">
        <label for="case_number_input">Case Number Input Field</label>
        <input type="text" class="form-control" id="case_number_input" name="case_number_input">
      </div>

      <div class="mb-3">
        <label for="search_button_selector">Search Button Selector</label>
        <input type="text" class="form-control" id="search_button_selector" name="search_button_selector">
      </div>

      <div class="mb-3">
        <label for="result_row_selector">Result Row Selector</label>
        <input type="text" class="form-control" id="result_row_selector" name="result_row_selector">
      </div>

      <div class="mb-3">
        <label for="events_table_selector">Events Table Selector</label>
        <input type="text" class="form-control" id="events_table_selector" name="events_table_selector">
      </div>

      <div class="mb-3">
        <label for="events_column_count">Number of Columns in Events Table</label>
        <input type="number" class="form-control" id="events_column_count" name="events_column_count">
      </div>

      <div class="mb-3">
        <label for="pre_search_click_selector">Pre-Search Click Selector (optional)</label>
        <input type="text" class="form-control" id="pre_search_click_selector" name="pre_search_click_selector">
      </div>
    </div>

    <!--- CAPTCHA --->
    <div class="mb-4">
      <h3>CAPTCHA Configuration</h3>

      <div class="mb-3">
        <label for="captcha_type">CAPTCHA Type</label>
        <input type="text" class="form-control" id="captcha_type" name="captcha_type">
      </div>

      <div class="mb-3">
        <label for="captcha_image_selector">CAPTCHA Image Selector</label>
        <input type="text" class="form-control" id="captcha_image_selector" name="captcha_image_selector">
      </div>

      <div class="mb-3">
        <label for="captcha_input_selector">CAPTCHA Input Field Selector</label>
        <input type="text" class="form-control" id="captcha_input_selector" name="captcha_input_selector">
      </div>

      <div class="mb-3">
        <label for="captcha_submit_selector">CAPTCHA Submit Button Selector</label>
        <input type="text" class="form-control" id="captcha_submit_selector" name="captcha_submit_selector">
      </div>
    </div>

    <!--- Optional Case Fields --->
    <div class="mb-4">
      <h3>Optional Case Metadata</h3>

      <div class="mb-3">
        <label for="case_link_selector">Case Link Selector</label>
        <input type="text" class="form-control" id="case_link_selector" name="case_link_selector">
      </div>

      <div class="mb-3">
        <label for="case_name_selector">Case Name Selector</label>
        <input type="text" class="form-control" id="case_name_selector" name="case_name_selector">
      </div>

      <div class="mb-3">
        <label for="court_name_selector">Court Name Selector</label>
        <input type="text" class="form-control" id="court_name_selector" name="court_name_selector">
      </div>

      <div class="mb-3">
        <label for="case_type_selector">Case Type Selector</label>
        <input type="text" class="form-control" id="case_type_selector" name="case_type_selector">
      </div>

      <div class="mb-3">
        <label for="event_col_0_label">Event Column 1 Label</label>
        <input type="text" class="form-control" id="event_col_0_label" name="event_col_0_label">
      </div>

      <div class="mb-3">
        <label for="event_col_1_label">Event Column 2 Label</label>
        <input type="text" class="form-control" id="event_col_1_label" name="event_col_1_label">
      </div>

      <div class="mb-3">
        <label for="event_col_2_label">Event Column 3 Label</label>
        <input type="text" class="form-control" id="event_col_2_label" name="event_col_2_label">
      </div>
    </div>

    <button type="submit" class="btn btn-primary">Save Tool Configuration</button>
  </form>
</div>

<script>
  document.addEventListener("DOMContentLoaded", function () {
    const loginCheckbox = document.getElementById("isLogin");
    const loginSection = document.getElementById("loginSection");

    function toggleLoginSection() {
      loginSection.style.display = loginCheckbox.checked ? "block" : "none";
    }

    loginCheckbox.addEventListener("change", toggleLoginSection);
    toggleLoginSection(); // initial load
  });
</script>

<cfinclude template="footer_script.cfm">
</body>
</html>
