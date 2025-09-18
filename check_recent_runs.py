#!/usr/bin/env python3
"""
Check the timing and patterns of task_runs creation
"""
import pyodbc

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    print("=== Recent task_runs for both RSS scripts ===")
    
    cursor.execute("""
        SELECT 
            st.filename,
            tr.id,
            tr.timestamp_started,
            tr.timestamp_ended,
            tr.status,
            tr.summary
        FROM docketwatch.dbo.task_runs tr
        JOIN docketwatch.dbo.scheduled_task st ON tr.fk_scheduled_task = st.id
        WHERE st.filename IN ('docketwatch_rss_trigger', 'docketwatch_rss_trigger_plus')
        AND tr.timestamp_started >= DATEADD(hour, -6, GETDATE())
        ORDER BY tr.timestamp_started DESC
    """)
    
    runs = cursor.fetchall()
    print(f"Found {len(runs)} recent runs in the last 6 hours:")
    print()
    
    for run in runs:
        filename = run[0]
        run_id = run[1]
        started = run[2]
        ended = run[3]
        status = run[4]
        summary = run[5] or "No summary"
        
        duration = ""
        if ended and started:
            delta = ended - started
            duration = f" ({delta.total_seconds():.1f}s)"
        
        print(f"{filename}:")
        print(f"  ID: {run_id}, Started: {started}{duration}")
        print(f"  Status: {status}, Summary: {summary}")
        print()
    
    # Check if there are any scheduled tasks running both scripts
    print("=== Checking scheduled execution patterns ===")
    cursor.execute("""
        SELECT 
            st.filename,
            st.task_name,
            COUNT(tr.id) as run_count,
            MAX(tr.timestamp_started) as last_run
        FROM docketwatch.dbo.scheduled_task st
        LEFT JOIN docketwatch.dbo.task_runs tr ON st.id = tr.fk_scheduled_task
        WHERE st.filename IN ('docketwatch_rss_trigger', 'docketwatch_rss_trigger_plus')
        GROUP BY st.filename, st.task_name
    """)
    
    schedules = cursor.fetchall()
    for sched in schedules:
        print(f"{sched[0]}: {sched[2]} total runs, last: {sched[3]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()