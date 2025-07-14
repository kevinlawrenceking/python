import pyodbc
import subprocess
import time

# Path to your pacer_single.py script
PYTHON_PATH = r"C:\Program Files\Python312\python.exe"
SCRIPT_PATH = r"U:\docketwatch\python\pacer_single.py"

# Connect to DB and get case IDs
def get_case_ids():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id 
        FROM docketwatch.dbo.cases 
        WHERE fk_tool = 2 
          AND case_url IS NOT NULL 
          AND case_url <> '' 
          AND status = 'Tracked' 
          AND id NOT IN (SELECT fk_cases FROM docketwatch.dbo.case_events)
    """)
    return [row[0] for row in cursor.fetchall()]

# Run pacer_single.py for each ID
def run_cases():
    ids = get_case_ids()
    print(f"Running {len(ids)} case(s)...")
    for case_id in ids:
        print(f"Running case ID: {case_id}")
        subprocess.call([PYTHON_PATH, SCRIPT_PATH, str(case_id)])
        time.sleep(1)  # slight pause between runs to avoid overlap

if __name__ == "__main__":
    run_cases()
