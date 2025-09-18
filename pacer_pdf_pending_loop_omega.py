import pyodbc
import subprocess
import time

# --- Database connection ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Query to find case_events that need processing (no documents OR pending documents) ---
cursor.execute("""
    SELECT TOP 50 
        ce.id,
        ce.event_no,
        ce.event_description,
        ce.event_date,
        c.case_number,
        CASE 
            WHEN d.doc_uid IS NULL THEN 'NO_DOCS'
            WHEN d.rel_path = 'pending' THEN 'PENDING'
            ELSE 'OTHER'
        END as status,
        COUNT(d.doc_uid) as doc_count
    FROM docketwatch.dbo.case_events ce
    INNER JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
    INNER JOIN docketwatch.dbo.tools t ON t.id = c.fk_tool
    LEFT JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_event
    WHERE t.tool_name = 'Pacer'
        AND ce.event_url IS NOT NULL 
        AND ce.event_url != ''
        AND (
            d.doc_uid IS NULL  -- No documents (need metadata)
            OR d.rel_path = 'pending'  -- Pending documents (need download)
        )
    GROUP BY ce.id, 
        ce.event_no,
        ce.event_description,
        ce.event_date,
        c.case_number,
        CASE 
            WHEN d.doc_uid IS NULL THEN 'NO_DOCS'
            WHEN d.rel_path = 'pending' THEN 'PENDING'
            ELSE 'OTHER'
        END
    ORDER BY ce.event_date DESC, ce.id DESC
""")
case_events = cursor.fetchall()
print(f"Found {len(case_events)} case_events that need processing.")

# --- Process each case_event with both scripts sequentially ---
for row in case_events:
    case_id = row.id
    event_no = row.event_no
    case_number = row.case_number
    status = row.status
    doc_count = row.doc_count
    
    print(f"\n[INFO] Processing case_event ID: {case_id} (Event {event_no}, Case {case_number}, Status: {status}, Docs: {doc_count})")
    
    # STEP 1: Always run metadata extraction first
    print(f"[STEP 1] Running extract_pacer_pdf_metadata.py for case_event: {case_id}")
    try:
        result = subprocess.run([
            "C:\\Program Files\\Python312\\python.exe",
            "u:\\docketwatch\\python\\extract_pacer_pdf_metadata.py",
            str(case_id)
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode == 0:
            print(f"[STEP 1] Metadata extraction completed successfully for {case_id}")
        else:
            print(f"[ERROR] Metadata extraction failed on case_event {case_id}:")
            print(f"  Return code: {result.returncode}")
            print(f"  STDOUT: {result.stdout[-500:]}")  # Last 500 chars
            print(f"  STDERR: {result.stderr[-500:]}")  # Last 500 chars
            continue  # Skip to next case_event if metadata fails
            
        time.sleep(5)  # Wait longer before next step to ensure Chrome cleanup
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Metadata extraction timed out on case_event {case_id}")
        continue
    except Exception as e:
        print(f"[ERROR] Metadata extraction exception on case_event {case_id}: {e}")
        continue
    
    # STEP 2: Run PDF download script
    print(f"[STEP 2] Running process_pacer_event_pdf_final.py for case_event: {case_id}")
    try:
        result = subprocess.run([
            "C:\\Program Files\\Python312\\python.exe",
            "u:\\docketwatch\\python\\process_pacer_event_pdf_final.py",
            str(case_id)
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode == 0:
            print(f"[STEP 2] PDF download completed successfully for {case_id}")
        else:
            print(f"[ERROR] PDF download failed on case_event {case_id}:")
            print(f"  Return code: {result.returncode}")
            print(f"  STDOUT: {result.stdout[-500:]}")  # Last 500 chars
            print(f"  STDERR: {result.stderr[-500:]}")  # Last 500 chars
            
        time.sleep(5)  # Wait longer before next case_event to ensure Chrome cleanup
    except subprocess.TimeoutExpired:
        print(f"[ERROR] PDF download timed out on case_event {case_id}")
    except Exception as e:
        print(f"[ERROR] PDF download exception on case_event {case_id}: {e}")
    
    print(f"[COMPLETE] Finished processing case_event {case_id}")
    print("-" * 60)

cursor.close()
conn.close()