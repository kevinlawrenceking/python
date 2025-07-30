<!--- Supreme Court Monitor Dashboard --->
<!--- Place this in your DocketWatch ColdFusion application --->

<cfparam name="url.refresh" default="30">

<!DOCTYPE html>
<html>
<head>
    <title>Supreme Court Monitor Dashboard</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="<cfoutput>#url.refresh#</cfoutput>">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .header { 
            text-align: center; 
            margin-bottom: 30px; 
            border-bottom: 2px solid #1976d2; 
            padding-bottom: 15px; 
        }
        .status-card { 
            border: 2px solid #ddd; 
            border-radius: 8px; 
            padding: 20px; 
            margin: 15px 0; 
            transition: all 0.3s ease; 
        }
        .status-ok { border-color: #4caf50; background-color: #f1f8e9; }
        .status-alert { border-color: #ff9800; background-color: #fff3e0; animation: pulse 2s infinite; }
        .status-error { border-color: #f44336; background-color: #ffebee; }
        .status-pending { border-color: #2196f3; background-color: #e3f2fd; }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(255, 152, 0, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0); }
        }
        
        .case-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .case-number { color: #666; font-size: 14px; }
        .status-badge { 
            display: inline-block; 
            padding: 4px 12px; 
            border-radius: 20px; 
            color: white; 
            font-weight: bold; 
            font-size: 12px; 
            margin-bottom: 10px; 
        }
        .badge-ok { background-color: #4caf50; }
        .badge-alert { background-color: #ff9800; }
        .badge-error { background-color: #f44336; }
        .badge-pending { background-color: #2196f3; }
        
        .info-grid { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 15px; 
            margin-top: 15px; 
        }
        .info-item { background: #f8f9fa; padding: 10px; border-radius: 4px; }
        .info-label { font-weight: bold; color: #555; }
        .info-value { color: #333; margin-top: 5px; }
        
        .refresh-info { 
            text-align: center; 
            margin-top: 20px; 
            padding: 10px; 
            background: #e8f4fd; 
            border-radius: 4px; 
            color: #1976d2; 
        }
        .manual-refresh { 
            display: inline-block; 
            margin-left: 10px; 
            padding: 5px 15px; 
            background: #1976d2; 
            color: white; 
            text-decoration: none; 
            border-radius: 4px; 
            font-size: 12px; 
        }
        .manual-refresh:hover { background: #1565c0; }
        
        .last-proceedings { 
            margin-top: 15px; 
            padding: 10px; 
            background: #f0f8ff; 
            border-left: 4px solid #1976d2; 
        }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1>Supreme Court Monitor Dashboard</h1>
        <p>Real-time monitoring of Supreme Court case proceedings</p>
        <p><strong>Auto-refresh:</strong> Every <cfoutput>#url.refresh#</cfoutput> seconds 
           <a href="?refresh=10" class="manual-refresh">10s</a>
           <a href="?refresh=30" class="manual-refresh">30s</a>
           <a href="?refresh=60" class="manual-refresh">60s</a>
           <a href="?" class="manual-refresh">Refresh Now</a>
        </p>
    </div>

    <cfquery name="getMonitorStatus" datasource="reach">
        SELECT 
            case_number,
            case_name,
            status,
            message,
            last_check,
            proceedings_count,
            last_proceeding_date,
            DATEDIFF(minute, last_check, GETDATE()) as minutes_ago
        FROM dbo.supreme_court_monitor_status
        ORDER BY last_check DESC
    </cfquery>

    <cfif getMonitorStatus.recordCount EQ 0>
        <div class="status-card status-error">
            <div class="case-title">No Monitor Data Found</div>
            <p>The Supreme Court monitor has not run yet or the database table needs to be created.</p>
        </div>
    <cfelse>
        <cfloop query="getMonitorStatus">
            <div class="status-card status-#LCase(status)#">
                <div class="case-title">
                    <cfif Len(case_name)>
                        #case_name#
                    <cfelse>
                        Case #case_number#
                    </cfif>
                </div>
                <div class="case-number">Case Number: #case_number#</div>
                
                <span class="status-badge badge-#LCase(status)#">#UCase(status)#</span>
                
                <div class="info-value" style="margin: 10px 0; font-size: 16px;">
                    #message#
                </div>
                
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Last Check</div>
                        <div class="info-value">
                            #DateFormat(last_check, "mm/dd/yyyy")# 
                            #TimeFormat(last_check, "h:mm:ss tt")#
                            <br><small>(#minutes_ago# minutes ago)</small>
                        </div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Total Proceedings</div>
                        <div class="info-value">#proceedings_count# entries</div>
                    </div>
                </div>
                
                <cfif Len(last_proceeding_date)>
                    <div class="last-proceedings">
                        <strong>Latest Proceeding:</strong> #last_proceeding_date#
                    </div>
                </cfif>
            </div>
        </cfloop>
    </cfif>

    <div class="refresh-info">
        <strong>Last Updated:</strong> <cfoutput>#DateFormat(Now(), "mm/dd/yyyy")# #TimeFormat(Now(), "h:mm:ss tt")#</cfoutput>
        <br>Page automatically refreshes every <cfoutput>#url.refresh#</cfoutput> seconds
    </div>

    <!--- Alert History Section --->
    <cfquery name="getRecentAlerts" datasource="reach">
        SELECT TOP 10
            case_number,
            status,
            message,
            last_check
        FROM dbo.supreme_court_monitor_status
        WHERE status = 'ALERT'
        ORDER BY last_check DESC
    </cfquery>

    <cfif getRecentAlerts.recordCount GT 0>
        <div style="margin-top: 30px;">
            <h3>Recent Alerts</h3>
            <cfloop query="getRecentAlerts">
                <div style="padding: 10px; margin: 5px 0; background: #fff3e0; border-left: 4px solid #ff9800;">
                    <strong>#case_number#:</strong> #message#
                    <br><small>#DateFormat(last_check, "mm/dd/yyyy")# #TimeFormat(last_check, "h:mm:ss tt")#</small>
                </div>
            </cfloop>
        </div>
    </cfif>
</div>

<script>
    // Visual/audio alert for new alerts
    <cfif getMonitorStatus.recordCount GT 0>
        <cfloop query="getMonitorStatus">
            <cfif status EQ "ALERT">
                // You could add audio alert here
                // new Audio('/sounds/alert.wav').play();
                
                // Flash title for attention
                let originalTitle = document.title;
                let flashTitle = function() {
                    document.title = document.title === originalTitle ? '🚨 ALERT - Supreme Court Monitor' : originalTitle;
                };
                setInterval(flashTitle, 1000);
            </cfif>
        </cfloop>
    </cfif>
</script>

</body>
</html>
