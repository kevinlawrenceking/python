import os
import pyodbc
import shutil

FINAL_PDF_DIR = r"\\10.146.176.84\general\mediaroot\pacer_pdfs"

# --- Database Connection ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        id,
        pacer_doc_id,
        local_pdf_filename,
        CAST(pacer_doc_id AS VARCHAR) + '.pdf' AS correct_local_pdf_filename
    FROM docketwatch.dbo.case_events_pdf 
    WHERE isDownloaded = 1
      AND CAST(pacer_doc_id AS VARCHAR) + '.pdf' <> local_pdf_filename
""")

rows = cursor.fetchall()
renamed = 0
skipped = 0

for row in rows:
    pdf_id = row.id
    old_filename = row.local_pdf_filename
    correct_filename = row.correct_local_pdf_filename

    old_path = os.path.join(FINAL_PDF_DIR, old_filename)
    new_path = os.path.join(FINAL_PDF_DIR, correct_filename)

    try:
        if not os.path.exists(old_path):
            print(f"SKIPPED: Missing file on disk → {old_filename}")
            skipped += 1
            continue

        if os.path.exists(new_path):
            print(f"SKIPPED: File already exists with correct name → {correct_filename}")
            skipped += 1
            continue

        shutil.move(old_path, new_path)
        print(f"RENAMED: {old_filename} → {correct_filename}")

        cursor.execute("""
            UPDATE docketwatch.dbo.case_events_pdf
            SET local_pdf_filename = ?
            WHERE id = ?
        """, (correct_filename, pdf_id))
        renamed += 1

    except Exception as e:
        print(f"ERROR: Failed to process {old_filename} → {e}")
        skipped += 1

conn.commit()
cursor.close()
conn.close()

print(f"\nFix complete. Renamed: {renamed}, Skipped/Error: {skipped}")
