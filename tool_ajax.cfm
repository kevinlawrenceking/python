<cfcontent type="application/json" />
<cfset tools = []>

<cfquery name="getTools" datasource="reach">
    SELECT 
        [id], [tool_name], [api_base_url], [api_key], [auth_method],
        [login_url], [username], [pass], [search_url], [owners], [fk_county],
        [addNew], [isLogin],[login_checkbox],
        [captcha_type], [captcha_image_selector], [captcha_input_selector], [captcha_submit_selector],
        [case_number_input], [search_button_selector], [result_row_selector], [case_link_selector],
        [case_name_selector], [court_name_selector], [case_type_selector],
        [events_table_selector], [event_col_0_label], [event_col_1_label], [event_col_2_label],
        [events_column_count], [pre_search_click_selector], [username_selector], [password_selector]
    FROM [docketwatch].[dbo].[tools]
</cfquery>

<cfloop query="getTools">
    <cfset arrayAppend(tools, {
        "tool_id": getTools.id,
        "tool_name": getTools.tool_name,
        "api_base_url": getTools.api_base_url,
        "api_key": getTools.api_key,
        "auth_method": getTools.auth_method,
        "login_url": getTools.login_url,
        "username": getTools.username,
        "pass": getTools.pass,
        "search_url": getTools.search_url,
        "owners": getTools.owners,
        "fk_county": getTools.fk_county,
        "addNew": getTools.addNew,
        "isLogin": getTools.isLogin,
        "captcha_type": getTools.captcha_type,
        "captcha_image_selector": getTools.captcha_image_selector,
        "captcha_input_selector": getTools.captcha_input_selector,
        "captcha_submit_selector": getTools.captcha_submit_selector,
        "case_number_input": getTools.case_number_input,
        "search_button_selector": getTools.search_button_selector,
        "result_row_selector": getTools.result_row_selector,
        "case_link_selector": getTools.case_link_selector,
        "case_name_selector": getTools.case_name_selector,
        "court_name_selector": getTools.court_name_selector,
        "case_type_selector": getTools.case_type_selector,
        "events_table_selector": getTools.events_table_selector,
        "event_col_0_label": getTools.event_col_0_label,
        "event_col_1_label": getTools.event_col_1_label,
        "event_col_2_label": getTools.event_col_2_label,
        "events_column_count": getTools.events_column_count,
        "pre_search_click_selector": getTools.pre_search_click_selector,
        "login_checkbox": getTools.login_checkbox,
        "username_selector": getTools.username_selector,
        "password_selector": getTools.password_selector

    })>
</cfloop>

<cfoutput>#serializeJSON(tools)#</cfoutput>
