<cfcontent type="application/json" />

<cftry>
    <!--- Raw input and validation --->
    <cfset rawData = getHttpRequestData().content>
    <cfif NOT len(trim(rawData))>
        <cfoutput>#serializeJSON({ "success": false, "message": "No JSON body received." })#</cfoutput>
        <cfabort>
    </cfif>

    <cfset formData = deserializeJSON(rawData)>

    <!--- Normalize tool_id --->
    <cfset tool_id = trim(formData.tool_id ?: "")>
    <cfif tool_id EQ "undefined"><cfset tool_id = ""></cfif>

    <!--- Required fields --->
    <cfset tool_name     = trim(formData.tool_name ?: "")>
    <cfif len(tool_name) EQ 0>
        <cfoutput>#serializeJSON({ "success": false, "message": "Tool name is required." })#</cfoutput>
        <cfabort>
    </cfif>

    <!--- Duplicate name check --->
    <cfquery name="checkDup" datasource="reach">
        SELECT id FROM docketwatch.dbo.tools
        WHERE tool_name = <cfqueryparam value="#tool_name#" cfsqltype="cf_sql_varchar">
        <cfif len(tool_id)>
            AND id <> <cfqueryparam value="#tool_id#" cfsqltype="cf_sql_integer">
        </cfif>
    </cfquery>
    <cfif checkDup.recordCount>
        <cfoutput>#serializeJSON({ "success": false, "message": "A tool with that name already exists." })#</cfoutput>
        <cfabort>
    </cfif>

    <!--- Optional fields --->
    <cfset api_base_url  = trim(formData.api_base_url ?: "")>
    <cfset api_key       = trim(formData.api_key ?: "")>
    <cfset auth_method   = trim(formData.auth_method ?: "")>
    <cfset login_url     = trim(formData.login_url ?: "")>
    <cfset username      = trim(formData.username ?: "")>
    <cfset pass          = trim(formData.pass ?: "")>
    <cfset search_url    = trim(formData.search_url ?: "")>
    <cfset owners        = trim(formData.owners ?: "")>
    <cfset fk_county     = val(formData.fk_county ?: 0)>
    <cfset addNew        = yesNoFormat(formData.addNew ?: false)>
    <cfset isLogin       = yesNoFormat(formData.isLogin ?: false)>
    <cfset login_checkbox = trim(formData.login_checkbox ?: "")>

    <cfset username_selector = trim(formData.username_selector ?: "")>
    <cfset password_selector = trim(formData.password_selector ?: "")>  

    <!--- Selectors --->
    <cfset case_number_input        = trim(formData.case_number_input ?: "")>
    <cfset search_button_selector   = trim(formData.search_button_selector ?: "")>
    <cfset result_row_selector      = trim(formData.result_row_selector ?: "")>
    <cfset case_link_selector       = trim(formData.case_link_selector ?: "")>
    <cfset case_name_selector       = trim(formData.case_name_selector ?: "")>
    <cfset court_name_selector      = trim(formData.court_name_selector ?: "")>
    <cfset case_type_selector       = trim(formData.case_type_selector ?: "")>
    <cfset events_table_selector    = trim(formData.events_table_selector ?: "")>
    <cfset event_col_0_label        = trim(formData.event_col_0_label ?: "")>
    <cfset event_col_1_label        = trim(formData.event_col_1_label ?: "")>
    <cfset event_col_2_label        = trim(formData.event_col_2_label ?: "")>
    <cfset events_column_count      = val(formData.events_column_count ?: 0)>
    <cfset pre_search_click_selector = trim(formData.pre_search_click_selector ?: "")>

    <!--- CAPTCHA ---> 
    <cfset captcha_type             = trim(formData.captcha_type ?: "")>
    <cfset captcha_image_selector  = trim(formData.captcha_image_selector ?: "")>
    <cfset captcha_input_selector  = trim(formData.captcha_input_selector ?: "")>
    <cfset captcha_submit_selector = trim(formData.captcha_submit_selector ?: "")>

    <!--- Save to DB --->
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
                owners = <cfqueryparam value="#owners#" cfsqltype="cf_sql_varchar">,
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
                <cfqueryparam value="#owners#" cfsqltype="cf_sql_varchar">,
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

    <cfoutput>#serializeJSON({ "success": true })#</cfoutput>

<cfcatch type="any">
    <cfset errorDump = {
        success: false,
        type: cfcatch.type,
        message: cfcatch.message,
        detail: cfcatch.detail,
        errorCode: cfcatch.errorCode,
        sql: structKeyExists(cfcatch, "sql") ? cfcatch.sql : "",
        stackTrace: cfcatch.tagContext
    }>
    <cfoutput>#serializeJSON(errorDump)#</cfoutput>
</cfcatch>
</cftry>
