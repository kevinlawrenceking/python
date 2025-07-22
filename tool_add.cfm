<cfquery name="insertTool" datasource="reach">
    INSERT INTO docketwatch.dbo.tools (
        tool_name
    ) OUTPUT INSERTED.id
    VALUES (
        'New Tool'
    )
</cfquery>

<cflocation url="tool_setup.cfm?id=#insertTool.id#" addtoken="false">
