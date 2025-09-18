#!/usr/bin/env python3
"""
Check the scheduled task configuration differences
"""
import pyodbc

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    print("=== Scheduled Task Configuration Comparison ===")
    
    cursor.execute("""
        SELECT 
            id,
            filename,
            task_name,
            schedule_expression,
            active,
            last_run,
            next_run,
            description
        FROM docketwatch.dbo.scheduled_task
        WHERE filename IN ('docketwatch_rss_trigger', 'docketwatch_rss_trigger_plus')
        ORDER BY filename
    """)
    
    tasks = cursor.fetchall()
    
    for task in tasks:
        print(f"\nTask: {task.filename}")
        print(f"  ID: {task.id}")
        print(f"  Name: {task.task_name}")
        print(f"  Active: {task.active}")
        print(f"  Schedule: {task.schedule_expression}")
        print(f"  Last Run: {task.last_run}")
        print(f"  Next Run: {task.next_run}")
        print(f"  Description: {task.description}")
    
    # Check execution frequency
    print("\n=== Execution Frequency Analysis ===")
    cursor.execute("""
        SELECT 
            st.filename,
            COUNT(tr.id) as total_runs,
            COUNT(CASE WHEN tr.timestamp_started >= DATEADD(day, -7, GETDATE()) THEN 1 END) as runs_last_7_days,
            COUNT(CASE WHEN tr.timestamp_started >= DATEADD(hour, -24, GETDATE()) THEN 1 END) as runs_last_24_hours,
            MIN(tr.timestamp_started) as first_run,
            MAX(tr.timestamp_started) as last_run
        FROM docketwatch.dbo.scheduled_task st
        LEFT JOIN docketwatch.dbo.task_runs tr ON st.id = tr.fk_scheduled_task
        WHERE st.filename IN ('docketwatch_rss_trigger', 'docketwatch_rss_trigger_plus')
        GROUP BY st.filename
    """)
    
    stats = cursor.fetchall()
    for stat in stats:
        print(f"\n{stat.filename}:")
        print(f"  Total runs: {stat.total_runs}")
        print(f"  Runs last 7 days: {stat.runs_last_7_days}")
        print(f"  Runs last 24 hours: {stat.runs_last_24_hours}")
        print(f"  First run: {stat.first_run}")
        print(f"  Last run: {stat.last_run}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()