<!DOCTYPE html>
<html>
<head>
    <title>AI Success Rate Dashboard - DAMZ Headline Optimization</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #007bff;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-card h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
        }
        .metric-card .number {
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-card .percentage {
            font-size: 18px;
            opacity: 0.9;
        }
        .success { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); }
        .warning { background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%); }
        .info { background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); }
        .danger { background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%); }
        
        .section {
            margin: 30px 0;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #fafafa;
        }
        .section h2 {
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background-color: white;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #007bff;
            color: white;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .status-good { color: #4CAF50; font-weight: bold; }
        .status-bad { color: #f44336; font-weight: bold; }
        .status-neutral { color: #757575; }
        .refresh-btn {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background-color: #0056b3;
        }
        .last-updated {
            text-align: right;
            color: #666;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1>🤖 AI Success Rate Dashboard</h1>
        <p>DAMZ Headline Optimization Analysis</p>
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Data</button>
    </div>

    <cfquery name="getOverallStats" datasource="docketwatch">
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN headline_optimized IS NOT NULL THEN 1 END) as batch1_processed,
            COUNT(CASE WHEN headline_v2 IS NOT NULL THEN 1 END) as batch2_processed,
            COUNT(CASE WHEN headline_final IS NOT NULL THEN 1 END) as user_reviewed,
            COUNT(CASE WHEN headline_optimized = headline_final THEN 1 END) as batch1_perfect,
            COUNT(CASE WHEN headline_v2 = headline_final AND headline_optimized != headline_final THEN 1 END) as batch2_perfect,
            COUNT(CASE WHEN flagged = 1 THEN 1 END) as flagged_for_processing
        FROM docketwatch.dbo.damz_test
        WHERE headline IS NOT NULL
    </cfquery>

    <!-- Key Metrics Cards -->
    <div class="metrics-grid">
        <div class="metric-card info">
            <h3>Total Records</h3>
            <div class="number"><cfoutput>#getOverallStats.total_records#</cfoutput></div>
        </div>
        
        <div class="metric-card warning">
            <h3>Flagged for Processing</h3>
            <div class="number"><cfoutput>#getOverallStats.flagged_for_processing#</cfoutput></div>
        </div>

        <div class="metric-card success">
            <h3>Batch 1 Success Rate</h3>
            <div class="number">
                <cfoutput>
                    <cfif getOverallStats.user_reviewed GT 0>
                        #round((getOverallStats.batch1_perfect / getOverallStats.user_reviewed) * 100)#%
                    <cfelse>
                        N/A
                    </cfif>
                </cfoutput>
            </div>
            <div class="percentage">
                <cfoutput>
                    #getOverallStats.batch1_perfect# of #getOverallStats.user_reviewed# perfect
                </cfoutput>
            </div>
        </div>

        <div class="metric-card success">
            <h3>Batch 2 Success Rate</h3>
            <div class="number">
                <cfoutput>
                    <cfset batch2_attempts = getOverallStats.user_reviewed - getOverallStats.batch1_perfect>
                    <cfif batch2_attempts GT 0>
                        #round((getOverallStats.batch2_perfect / batch2_attempts) * 100)#%
                    <cfelse>
                        N/A
                    </cfif>
                </cfoutput>
            </div>
            <div class="percentage">
                <cfoutput>
                    #getOverallStats.batch2_perfect# of #batch2_attempts# perfect
                </cfoutput>
            </div>
        </div>
    </div>

    <!-- Batch 1 Analysis -->
    <div class="section">
        <h2>📊 Batch 1 Analysis (Original AI Rules)</h2>
        <cfquery name="getBatch1Details" datasource="docketwatch">
            SELECT 
                fk_asset,
                headline,
                headline_optimized,
                headline_final,
                headline_type,
                CASE 
                    WHEN headline_optimized = headline_final THEN 'Perfect Match'
                    WHEN headline_final IS NULL THEN 'Not Reviewed'
                    ELSE 'Needs Improvement'
                END as status,
                CASE 
                    WHEN headline_optimized = headline_final THEN 1
                    ELSE 0
                END as is_perfect
            FROM docketwatch.dbo.damz_test
            WHERE headline_optimized IS NOT NULL
            ORDER BY 
                CASE 
                    WHEN headline_optimized = headline_final THEN 1
                    WHEN headline_final IS NULL THEN 2
                    ELSE 3
                END,
                fk_asset
        </cfquery>

        <table>
            <thead>
                <tr>
                    <th>Asset ID</th>
                    <th>Original Headline</th>
                    <th>AI Generated (Batch 1)</th>
                    <th>User Final</th>
                    <th>Type</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                <cfoutput query="getBatch1Details" maxrows="50">
                    <tr>
                        <td>#left(fk_asset, 8)#...</td>
                        <td title="#headline#">#left(headline, 30)#<cfif len(headline) GT 30>...</cfif></td>
                        <td title="#headline_optimized#">#left(headline_optimized, 30)#<cfif len(headline_optimized) GT 30>...</cfif></td>
                        <td title="#headline_final#">
                            <cfif headline_final NEQ "">
                                #left(headline_final, 30)#<cfif len(headline_final) GT 30>...</cfif>
                            <cfelse>
                                <em>Not reviewed</em>
                            </cfif>
                        </td>
                        <td>#headline_type#</td>
                        <td class="
                            <cfif status EQ 'Perfect Match'>status-good
                            <cfelseif status EQ 'Needs Improvement'>status-bad
                            <cfelse>status-neutral</cfif>
                        ">#status#</td>
                    </tr>
                </cfoutput>
                <cfif getBatch1Details.recordCount GT 50>
                    <tr><td colspan="6"><em>Showing first 50 records. Total: <cfoutput>#getBatch1Details.recordCount#</cfoutput></em></td></tr>
                </cfif>
            </tbody>
        </table>
    </div>

    <!-- Batch 2 Analysis -->
    <div class="section">
        <h2>🔄 Batch 2 Analysis (Improved AI Rules)</h2>
        <cfquery name="getBatch2Details" datasource="docketwatch">
            SELECT 
                fk_asset,
                headline,
                headline_optimized,
                headline_v2,
                headline_final,
                headline_type,
                CASE 
                    WHEN headline_v2 = headline_final THEN 'Perfect Match'
                    WHEN headline_v2 IS NULL THEN 'Not Processed'
                    WHEN headline_final IS NULL THEN 'Not Reviewed'
                    ELSE 'Still Needs Work'
                END as status
            FROM docketwatch.dbo.damz_test
            WHERE headline_optimized IS NOT NULL 
                AND headline_optimized != headline_final
            ORDER BY 
                CASE 
                    WHEN headline_v2 = headline_final THEN 1
                    WHEN headline_v2 IS NULL THEN 2
                    WHEN headline_final IS NULL THEN 3
                    ELSE 4
                END,
                fk_asset
        </cfquery>

        <table>
            <thead>
                <tr>
                    <th>Asset ID</th>
                    <th>Original</th>
                    <th>Batch 1 Failed</th>
                    <th>Batch 2 (v2)</th>
                    <th>User Final</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                <cfoutput query="getBatch2Details" maxrows="50">
                    <tr>
                        <td>#left(fk_asset, 8)#...</td>
                        <td title="#headline#">#left(headline, 25)#<cfif len(headline) GT 25>...</cfif></td>
                        <td title="#headline_optimized#">#left(headline_optimized, 25)#<cfif len(headline_optimized) GT 25>...</cfif></td>
                        <td title="#headline_v2#">
                            <cfif headline_v2 NEQ "">
                                #left(headline_v2, 25)#<cfif len(headline_v2) GT 25>...</cfif>
                            <cfelse>
                                <em>Not processed</em>
                            </cfif>
                        </td>
                        <td title="#headline_final#">#left(headline_final, 25)#<cfif len(headline_final) GT 25>...</cfif></td>
                        <td class="
                            <cfif status EQ 'Perfect Match'>status-good
                            <cfelseif status EQ 'Still Needs Work'>status-bad
                            <cfelse>status-neutral</cfif>
                        ">#status#</td>
                    </tr>
                </cfoutput>
                <cfif getBatch2Details.recordCount GT 50>
                    <tr><td colspan="6"><em>Showing first 50 records. Total: <cfoutput>#getBatch2Details.recordCount#</cfoutput></em></td></tr>
                </cfif>
            </tbody>
        </table>
    </div>

    <!-- Type Analysis -->
    <div class="section">
        <h2>📝 Headline Type Distribution</h2>
        <cfquery name="getTypeStats" datasource="docketwatch">
            SELECT 
                headline_type,
                COUNT(*) as count,
                COUNT(CASE WHEN headline_optimized = headline_final THEN 1 END) as batch1_success,
                COUNT(CASE WHEN headline_v2 = headline_final AND headline_optimized != headline_final THEN 1 END) as batch2_success
            FROM docketwatch.dbo.damz_test
            WHERE headline_type IS NOT NULL
            GROUP BY headline_type
            ORDER BY count DESC
        </cfquery>

        <table>
            <thead>
                <tr>
                    <th>Headline Type</th>
                    <th>Total Count</th>
                    <th>Batch 1 Successes</th>
                    <th>Batch 2 Successes</th>
                    <th>Overall Success Rate</th>
                </tr>
            </thead>
            <tbody>
                <cfoutput query="getTypeStats">
                    <tr>
                        <td><strong>#headline_type#</strong></td>
                        <td>#count#</td>
                        <td>#batch1_success#</td>
                        <td>#batch2_success#</td>
                        <td>
                            <cfset total_success = batch1_success + batch2_success>
                            <cfif count GT 0>
                                #round((total_success / count) * 100)#%
                            <cfelse>
                                0%
                            </cfif>
                        </td>
                    </tr>
                </cfoutput>
            </tbody>
        </table>
    </div>

    <!-- Summary Insights -->
    <div class="section">
        <h2>💡 Key Insights</h2>
        <cfquery name="getInsights" datasource="docketwatch">
            SELECT 
                COUNT(CASE WHEN headline_optimized IS NOT NULL AND headline_final IS NOT NULL THEN 1 END) as reviewed_count,
                COUNT(CASE WHEN headline_optimized = headline_final THEN 1 END) as batch1_perfect,
                COUNT(CASE WHEN headline_v2 = headline_final AND headline_optimized != headline_final THEN 1 END) as batch2_perfect,
                COUNT(CASE WHEN headline_optimized != headline_final AND (headline_v2 IS NULL OR headline_v2 != headline_final) THEN 1 END) as still_needs_work
            FROM docketwatch.dbo.damz_test
            WHERE headline_optimized IS NOT NULL
        </cfquery>

        <cfoutput query="getInsights">
            <ul>
                <li><strong>First Batch Performance:</strong> 
                    <cfif reviewed_count GT 0>
                        #round((batch1_perfect / reviewed_count) * 100)#% of headlines were perfect on first try (#batch1_perfect# out of #reviewed_count#)
                    <cfelse>
                        No reviewed records found
                    </cfif>
                </li>
                <li><strong>Second Batch Recovery:</strong> 
                    <cfset batch1_failures = reviewed_count - batch1_perfect>
                    <cfif batch1_failures GT 0>
                        #round((batch2_perfect / batch1_failures) * 100)#% of failed headlines were fixed in batch 2 (#batch2_perfect# out of #batch1_failures#)
                    <cfelse>
                        No failed headlines to recover
                    </cfif>
                </li>
                <li><strong>Overall AI Success:</strong> 
                    <cfset total_ai_success = batch1_perfect + batch2_perfect>
                    <cfif reviewed_count GT 0>
                        #round((total_ai_success / reviewed_count) * 100)#% of headlines required no human intervention (#total_ai_success# out of #reviewed_count#)
                    <cfelse>
                        No data available
                    </cfif>
                </li>
                <li><strong>Still Need Work:</strong> #still_needs_work# headlines still require manual correction after both AI attempts</li>
            </ul>
        </cfoutput>
    </div>

    <div class="last-updated">
        Last updated: <cfoutput>#dateFormat(now(), "mmm dd, yyyy")# at #timeFormat(now(), "h:mm tt")#</cfoutput>
    </div>
</div>

</body>
</html>
