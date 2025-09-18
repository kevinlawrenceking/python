import sys
import pyodbc
import subprocess
import time

def process_single_case_event(case_event_id):
    """Process a single case event through both metadata and PDF download steps"""
    
    # --- Database connection ---
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    # --- Query to get case event details ---
    cursor.execute("""
        SELECT 
            ce.id,
            ce.event_no,
            ce.event_description,
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
        WHERE ce.id = ? AND t.tool_name = 'Pacer'
        GROUP BY ce.id, ce.event_no, ce.event_description, c.case_number,
                 CASE 
                     WHEN d.doc_uid IS NULL THEN 'NO_DOCS'
                     WHEN d.rel_path = 'pending' THEN 'PENDING'
                     ELSE 'OTHER'
                 END
    """, case_event_id)
    
    row = cursor.fetchone()
    if not row:
        print(f"ERROR: Case event {case_event_id} not found or not a PACER event")
        cursor.close()
        conn.close()
        return False
    
    # Extract event details
    event_no = row.event_no
    case_number = row.case_number
    status = row.status
    doc_count = row.doc_count
    
    print(f"[INFO] Processing case_event ID: {case_event_id} (Event {event_no}, Case {case_number}, Status: {status}, Docs: {doc_count})")
    
    # STEP 1: Run metadata extraction
    print(f"[STEP 1] Running extract_pacer_pdf_file.py for case_event: {case_event_id}")
    try:
        subprocess.run([
            "C:\\Program Files\\Python312\\python.exe",
            "\\\\10.146.176.84\\general\\docketwatch\\python\\extract_pacer_pdf_file.py",
            str(case_event_id)
        ], check=True)
        print(f"[STEP 1] PDF file extraction completed successfully for {case_event_id}")
        time.sleep(3)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PDF file extraction failed on case_event {case_event_id}: {e}")
        cursor.close()
        conn.close()
        return False
    
    # STEP 2: Run PDF download
    print(f"[STEP 2] Running process_pacer_event_pdf_final.py for case_event: {case_event_id}")
    try:
        subprocess.run([
            "C:\\Program Files\\Python312\\python.exe",
            "\\\\10.146.176.84\\general\\docketwatch\\python\\process_pacer_event_pdf_final.py",
            str(case_event_id)
        ], check=True)
        print(f"[STEP 2] PDF download completed successfully for {case_event_id}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PDF download failed on case_event {case_event_id}: {e}")
        cursor.close()
        conn.close()
        return False
    
    print(f"[SUCCESS] Completed processing case_event {case_event_id}")
    cursor.close()
    conn.close()
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_single_case_event.py <case_event_id>")
        sys.exit(1)
    
    case_event_id = sys.argv[1]
    success = process_single_case_event(case_event_id)
    sys.exit(0 if success else 1)