#!/usr/bin/env python3
"""
Check scheduled_task table for RSS trigger
"""
import pyodbc
import os

script_filename = os.path.splitext(os.path.basename("docketwatch_rss_trigger.py"))[0]
print(f"Looking for script_filename: '{script_filename}'")

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    # Check what's in scheduled_task table
    cursor.execute("""
        SELECT id, filename, task_name
        FROM docketwatch.dbo.scheduled_task
        WHERE filename LIKE '%rss%'
    """)
    
    tasks = cursor.fetchall()
    print("\nScheduled tasks containing 'rss':")
    for task in tasks:
        print(f"  ID: {task.id}, Filename: '{task.filename}', Name: '{task.task_name}'")
    
    # Check exact match
    cursor.execute("""
        SELECT id, filename, task_name
        FROM docketwatch.dbo.scheduled_task
        WHERE filename = ?
    """, (script_filename,))
    
    exact_match = cursor.fetchone()
    if exact_match:
        print(f"\n✓ Found exact match: ID {exact_match.id}")
        
        # Check for recent task_runs
        cursor.execute("""
            SELECT TOP 5 r.id, r.start_time, r.end_time
            FROM docketwatch.dbo.task_runs r
            WHERE r.fk_scheduled_task = ?
            ORDER BY r.id DESC
        """, (exact_match.id,))
        
        runs = cursor.fetchall()
        print(f"Recent task runs: {len(runs)}")
        for run in runs:
            print(f"  Run ID: {run.id}, Start: {run.start_time}, End: {run.end_time}")
            
    else:
        print(f"\n✗ No exact match found for filename '{script_filename}'")
        
        # Check all filenames to see what's available
        cursor.execute("SELECT DISTINCT filename FROM docketwatch.dbo.scheduled_task ORDER BY filename")
        all_files = cursor.fetchall()
        print("\nAll scheduled task filenames:")
        for f in all_files:
            print(f"  '{f.filename}'")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()