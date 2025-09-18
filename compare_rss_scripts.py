#!/usr/bin/env python3
"""
Check why the 'plus' version works vs regular version
"""
import pyodbc
import os

# Check both scripts
scripts = [
    "docketwatch_rss_trigger",      # should be ID 46
    "docketwatch_rss_trigger_plus"  # should be ID 69
]

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    for script_filename in scripts:
        print(f"\n=== Checking {script_filename} ===")
        
        # Get scheduled_task info
        cursor.execute("""
            SELECT id, filename, task_name
            FROM docketwatch.dbo.scheduled_task
            WHERE filename = ?
        """, (script_filename,))
        
        task = cursor.fetchone()
        if task:
            task_id = task.id
            print(f"✓ Scheduled task ID: {task_id}")
            
            # Check recent task_runs
            cursor.execute("""
                SELECT TOP 5 r.id, r.timestamp_started, r.status
                FROM docketwatch.dbo.task_runs r
                WHERE r.fk_scheduled_task = ?
                ORDER BY r.id DESC
            """, (task_id,))
            
            runs = cursor.fetchall()
            print(f"Recent task_runs: {len(runs)}")
            for run in runs:
                print(f"  ID: {run.id}, Started: {run.timestamp_started}, Status: {run.status}")
                
            if runs:
                # Test the exact query used in the script
                cursor.execute("""
                    SELECT TOP 1 r.id as fk_task_run
                    FROM docketwatch.dbo.task_runs r
                    INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id
                    WHERE s.filename = ?
                    ORDER BY r.id DESC
                """, (script_filename,))
                
                result = cursor.fetchone()
                if result:
                    print(f"✓ Script query would return fk_task_run: {result[0]}")
                else:
                    print("✗ Script query returned no results")
            else:
                print("✗ No task_runs found - script would fail")
        else:
            print(f"✗ No scheduled_task found for {script_filename}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()