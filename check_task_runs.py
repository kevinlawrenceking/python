#!/usr/bin/env python3
"""
Check task_runs table structure and recent entries
"""
import pyodbc

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    # Get table structure
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'task_runs' 
        ORDER BY ORDINAL_POSITION
    """)
    
    columns = cursor.fetchall()
    print("task_runs table columns:")
    for col in columns:
        print(f"  {col.COLUMN_NAME}: {col.DATA_TYPE}")
    
    # Get recent task_runs for our scheduled task
    print(f"\nRecent task_runs for scheduled_task ID 46:")
    cursor.execute("""
        SELECT TOP 5 id, fk_scheduled_task, created_date
        FROM docketwatch.dbo.task_runs
        WHERE fk_scheduled_task = 46
        ORDER BY id DESC
    """)
    
    runs = cursor.fetchall()
    for run in runs:
        print(f"  Run ID: {run.id}, Created: {run.created_date}")
    
    if not runs:
        print("  No task_runs found for this scheduled_task")
        
        # Check if task_runs exist for other scheduled tasks
        cursor.execute("""
            SELECT COUNT(*) as total FROM docketwatch.dbo.task_runs
        """)
        total = cursor.fetchone()[0]
        print(f"  Total task_runs in table: {total}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()