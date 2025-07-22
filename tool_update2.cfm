<cfparam name="form.tool_id" default="">
<cfparam name="form.addNew" default="0">
<cfparam name="form.isLogin" default="0">
<cfset addNew = (isDefined("form.addNew") AND form.addNew EQ "on") ? 1 : 0>
<cfset isLogin = (isDefined("form.isLogin") AND form.isLogin EQ "on") ? 1 : 0>

    <cfquery datasource="reach">
        <cfif len(tool_id)>
            UPDATE docketwatch.dbo.tools SET 
                tool_name = <cfqueryparam value="#tool_name#" cfsqltype="cf_sql_varchar">,
                api_base_url = <cfqueryparam value="#api_base_url#" cfsqltype="cf_sql_varchar">,
                api_key = <cfqueryparam value="#api_key#" cfsqltype="cf_sql_longvarchar">,
                auth_method = <cfqueryparam value="#auth_method#" cfsqltype="cf_sql_varchar">,
                login_url = <cfqueryparam value="#login_url#" cfsqltype="cf_sql_varchar">,
                username = <cfqueryparam value="#username#" cfsqltype="cf_sql_nvarchar">,
                pass = <cfqueryparam value="#pass#" cfsqltype="cf_sql_nvarchar">,
                search_url = <cfqueryparam value="#search_url#" cfsqltype="cf_sql_varchar">,
           <!---     owners = <cfqueryparam value="#owners#" cfsqltype="cf_sql_varchar">, --->
                fk_county = <cfqueryparam value="#fk_county#" cfsqltype="cf_sql_integer">,
                login_checkbox = <cfqueryparam value="#login_checkbox#" cfsqltype="cf_sql_varchar">,
                addNew = <cfqueryparam value="#addNew#" cfsqltype="cf_sql_bit">,
                isLogin = <cfqueryparam value="#isLogin#" cfsqltype="cf_sql_bit">,
                case_number_input = <cfqueryparam value="#case_number_input#" cfsqltype="cf_sql_varchar">,
                search_button_selector = <cfqueryparam value="#search_button_selector#" cfsqltype="cf_sql_varchar">,
                result_row_selector = <cfqueryparam value="#result_row_selector#" cfsqltype="cf_sql_varchar">,
                case_link_selector = <cfqueryparam value="#case_link_selector#" cfsqltype="cf_sql_varchar">,
                case_name_selector = <cfqueryparam value="#case_name_selector#" cfsqltype="cf_sql_varchar">,
                court_name_selector = <cfqueryparam value="#court_name_selector#" cfsqltype="cf_sql_varchar">,
                case_type_selector = <cfqueryparam value="#case_type_selector#" cfsqltype="cf_sql_varchar">,
                events_table_selector = <cfqueryparam value="#events_table_selector#" cfsqltype="cf_sql_varchar">,
                event_col_0_label = <cfqueryparam value="#event_col_0_label#" cfsqltype="cf_sql_varchar">,
                event_col_1_label = <cfqueryparam value="#event_col_1_label#" cfsqltype="cf_sql_varchar">,
                event_col_2_label = <cfqueryparam value="#event_col_2_label#" cfsqltype="cf_sql_varchar">,
                events_column_count = <cfqueryparam value="#events_column_count#" cfsqltype="cf_sql_integer">,
                pre_search_click_selector = <cfqueryparam value="#pre_search_click_selector#" cfsqltype="cf_sql_varchar">,
                captcha_type = <cfqueryparam value="#captcha_type#" cfsqltype="cf_sql_varchar">,
                captcha_image_selector = <cfqueryparam value="#captcha_image_selector#" cfsqltype="cf_sql_varchar">,
                captcha_input_selector = <cfqueryparam value="#captcha_input_selector#" cfsqltype="cf_sql_varchar">,
                captcha_submit_selector = <cfqueryparam value="#captcha_submit_selector#" cfsqltype="cf_sql_varchar">,
                username_selector = <cfqueryparam value="#username_selector#" cfsqltype="cf_sql_varchar">,
                password_selector = <cfqueryparam value="#password_selector#" cfsqltype="cf_sql_varchar">

            WHERE id = <cfqueryparam value="#tool_id#" cfsqltype="cf_sql_integer">
        <cfelse>
            INSERT INTO docketwatch.dbo.tools (
                tool_name, api_base_url, api_key, auth_method, login_url, username, pass, search_url, owners,
                fk_county, addNew, isLogin,
                case_number_input, search_button_selector, result_row_selector, case_link_selector, case_name_selector,
                court_name_selector, case_type_selector, events_table_selector,
                event_col_0_label, event_col_1_label, event_col_2_label, events_column_count,
                pre_search_click_selector, captcha_type, captcha_image_selector, captcha_input_selector, captcha_submit_selector, login_checkbox, username_selector, password_selector
            ) VALUES (
                <cfqueryparam value="#tool_name#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#api_base_url#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#api_key#" cfsqltype="cf_sql_longvarchar">,
                <cfqueryparam value="#auth_method#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#login_url#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#username#" cfsqltype="cf_sql_nvarchar">,
                <cfqueryparam value="#pass#" cfsqltype="cf_sql_nvarchar">,
                <cfqueryparam value="#search_url#" cfsqltype="cf_sql_varchar">,
            <!---         <cfqueryparam value="#owners#" cfsqltype="cf_sql_varchar">, --->
                <cfqueryparam value="#fk_county#" cfsqltype="cf_sql_integer">,
                <cfqueryparam value="#addNew#" cfsqltype="cf_sql_bit">,
                <cfqueryparam value="#isLogin#" cfsqltype="cf_sql_bit">,
                <cfqueryparam value="#case_number_input#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#search_button_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#result_row_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#case_link_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#case_name_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#court_name_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#case_type_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#events_table_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#event_col_0_label#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#event_col_1_label#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#event_col_2_label#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#events_column_count#" cfsqltype="cf_sql_integer">,
                <cfqueryparam value="#pre_search_click_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#captcha_type#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#captcha_image_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#captcha_input_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#captcha_submit_selector#" cfsqltype="cf_sql_varchar">, 
                <cfqueryparam value="#login_checkbox#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#username_selector#" cfsqltype="cf_sql_varchar">,
                <cfqueryparam value="#password_selector#" cfsqltype="cf_sql_varchar">
            )
        </cfif>
    </cfquery>


<cflocation url="tools.cfm" />