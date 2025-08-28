import pyodbc
from datetime import datetime, timedelta

def get_gemini_usage_report(days=30):
    """Generate a comprehensive usage report for Gemini API calls"""
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    print(f"=== GEMINI API USAGE REPORT (Last {days} days) ===")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Overall summary
    cursor.execute("""
        SELECT 
            COUNT(*) as total_calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_calls,
            SUM(ISNULL(total_tokens, 0)) as total_tokens,
            SUM(ISNULL(cost_estimate, 0)) as total_cost,
            AVG(processing_time_ms) as avg_processing_time,
            MIN(call_timestamp) as first_call,
            MAX(call_timestamp) as last_call
        FROM docketwatch.dbo.gemini_api_log 
        WHERE call_timestamp >= DATEADD(day, -?, GETDATE())
    """, (days,))
    
    row = cursor.fetchone()
    if row and row[0] > 0:
        total_calls, successful, failed, total_tokens, total_cost, avg_time, first_call, last_call = row
        success_rate = (successful / total_calls * 100) if total_calls > 0 else 0
        
        print(f"OVERALL SUMMARY:")
        print(f"  Total API calls: {total_calls:,}")
        print(f"  Successful: {successful:,} ({success_rate:.1f}%)")
        print(f"  Failed: {failed:,}")
        print(f"  Total tokens used: {total_tokens:,}")
        print(f"  Total estimated cost: ${total_cost:.6f}")
        print(f"  Average processing time: {avg_time:.1f}ms")
        print(f"  First call: {first_call}")
        print(f"  Last call: {last_call}")
        print()
    
    # By script breakdown
    print("BY SCRIPT:")
    cursor.execute("""
        SELECT 
            script_name,
            model_name,
            COUNT(*) as calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
            SUM(ISNULL(total_tokens, 0)) as tokens,
            SUM(ISNULL(cost_estimate, 0)) as cost,
            AVG(processing_time_ms) as avg_time
        FROM docketwatch.dbo.gemini_api_log 
        WHERE call_timestamp >= DATEADD(day, -?, GETDATE())
        GROUP BY script_name, model_name
        ORDER BY calls DESC
    """, (days,))
    
    for row in cursor.fetchall():
        script, model, calls, successful, tokens, cost, avg_time = row
        success_rate = (successful / calls * 100) if calls > 0 else 0
        print(f"  {script} ({model}):")
        print(f"    Calls: {calls:,} ({success_rate:.1f}% success)")
        print(f"    Tokens: {tokens:,}")
        print(f"    Cost: ${cost:.6f}")
        print(f"    Avg time: {avg_time:.1f}ms")
        print()
    
    # Daily breakdown (last 7 days)
    print("DAILY BREAKDOWN (Last 7 days):")
    cursor.execute("""
        SELECT 
            CAST(call_timestamp AS DATE) as call_date,
            COUNT(*) as calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
            SUM(ISNULL(total_tokens, 0)) as tokens,
            SUM(ISNULL(cost_estimate, 0)) as cost
        FROM docketwatch.dbo.gemini_api_log 
        WHERE call_timestamp >= DATEADD(day, -7, GETDATE())
        GROUP BY CAST(call_timestamp AS DATE)
        ORDER BY call_date DESC
    """)
    
    for row in cursor.fetchall():
        date, calls, successful, tokens, cost = row
        success_rate = (successful / calls * 100) if calls > 0 else 0
        print(f"  {date}: {calls:,} calls ({success_rate:.1f}% success), {tokens:,} tokens, ${cost:.6f}")
    
    # Recent errors
    print("\nRECENT ERRORS (Last 24 hours):")
    cursor.execute("""
        SELECT TOP 10
            call_timestamp,
            script_name,
            fk_asset,
            error_message
        FROM docketwatch.dbo.gemini_api_log 
        WHERE success = 0 
        AND call_timestamp >= DATEADD(hour, -24, GETDATE())
        ORDER BY call_timestamp DESC
    """)
    
    errors = cursor.fetchall()
    if errors:
        for row in errors:
            timestamp, script, asset, error = row
            print(f"  {timestamp}: {script} (Asset: {asset}) - {error[:100]}")
    else:
        print("  No errors in last 24 hours")
    
    cursor.close()
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    get_gemini_usage_report(30)  # Last 30 days
