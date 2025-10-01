import pyodbc
import subprocess
import time

# --- Database connection ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Query to find case_events that need processing (no documents OR pending documents) ---
cursor.execute("""
    SELECT TOP 1 
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
        AND CAST(ce.event_date AS DATE) = CAST(GETDATE() AS DATE)  -- Only today's events
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
    
    # Show the event URL for debugging
    cursor.execute("SELECT event_url FROM docketwatch.dbo.case_events WHERE id = ?", (case_id,))
    event_url_result = cursor.fetchone()
    event_url = event_url_result[0] if event_url_result else "NULL"
    print(f"[DEBUG] Event URL: {event_url}")
    
    # For PENDING documents, we need to refresh metadata to get fresh URLs
    if status == 'PENDING':
        print(f"[INFO] Document status is PENDING - will refresh metadata to get fresh URLs")
    
    # STEP 1: Always run metadata extraction first (especially important for PENDING docs)
    print(f"[STEP 1] Running extract_pacer_pdf_metadata.py for case_event: {case_id}")
    try:
        # Force fresh session by running in completely isolated process with timeout
        result = subprocess.run([
            "python",
            "u:\\docketwatch\\python\\extract_pacer_pdf_metadata.py",
            str(case_id)
        ], check=True,
           cwd="u:\\docketwatch\\python",  # Ensure clean working directory
           env=None,  # Use clean environment
           timeout=300)  # 5 minute timeout to prevent hanging
        print(f"[STEP 1] Metadata extraction completed successfully for {case_id}")
        time.sleep(5)  # Longer wait for PENDING docs to ensure fresh URLs
        
        # Verify that documents were actually created
        cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE fk_case_event = ?", (case_id,))
        doc_count_after = cursor.fetchone()[0]
        print(f"[VERIFICATION] Documents found after metadata extraction: {doc_count_after}")
        
        # Check if any documents were created with 'purchased_pending' status (already-purchased documents)
        cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE fk_case_event = ? AND rel_path = 'purchased_pending'", (case_id,))
        purchased_pending_count = cursor.fetchone()[0]
        
        if purchased_pending_count > 0:
            print(f"[INFO] Found {purchased_pending_count} already-purchased documents that need special handling")
            print(f"[INFO] These documents will be handled by the enhanced PDF download script")
            print(f"[INFO] The PDF download script can now properly handle transaction receipt workflows")
        
        if doc_count_after == 0:
            print(f"[WARNING] No documents created by metadata extraction for case_event {case_id}")
            print(f"[WARNING] This suggests the metadata extraction found no PDFs or failed silently")
            continue  # Skip to next case_event since there are no documents to download
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Metadata extraction failed on case_event {case_id}: {e}")
        continue  # Skip to next case_event if metadata fails
    except subprocess.TimeoutExpired as e:
        print(f"[ERROR] Metadata extraction timed out on case_event {case_id}: {e}")
        print(f"[ERROR] This suggests network issues or PACER being unresponsive")
        continue  # Skip to next case_event if metadata times out
    
    # STEP 2: Run PDF download script
    print(f"[STEP 2] Running process_pacer_event_pdf_final.py for case_event: {case_id}")
    try:
        # Force fresh session by running in completely isolated process with timeout
        result = subprocess.run([
            "python",
            "u:\\docketwatch\\python\\process_pacer_event_pdf_final.py",
            str(case_id)
        ], check=True, 
           cwd="u:\\docketwatch\\python",  # Ensure clean working directory
           env=None,  # Use clean environment
           timeout=300)  # 5 minute timeout to prevent hanging
        print(f"[STEP 2] PDF download completed successfully for {case_id}")
        time.sleep(5)  # Longer wait to ensure session cleanup
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PDF download failed on case_event {case_id}: {e}")
        time.sleep(2)  # Brief pause even on error
    except subprocess.TimeoutExpired as e:
        print(f"[ERROR] PDF download timed out on case_event {case_id}: {e}")
        print(f"[ERROR] This suggests network issues or PACER being unresponsive")
        time.sleep(2)  # Brief pause even on timeout
    
    print(f"[COMPLETE] Finished processing case_event {case_id}")
    print("-" * 60)

cursor.close()
conn.close()