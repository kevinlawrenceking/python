import os
import pyodbc

# --- Config ---
DOCS_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"
DSN = "Docketwatch"

# --- Connect to DB ---
conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Find duplicates (except 1st per group) ---
cursor.execute("""
    WITH DupDocs AS (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY ocr_text_raw ORDER BY date_downloaded ASC) AS rn
        FROM docketwatch.dbo.documents
        WHERE ocr_text_raw IS NOT NULL
    )
    SELECT doc_uid, doc_id, fk_case, rel_path
    FROM DupDocs
    WHERE rn > 1
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} duplicate documents to delete.\n")

# --- Delete files and DB records ---
for row in rows:
    doc_uid, doc_id, fk_case, rel_path = row
    file_path = os.path.join(DOCS_DIR, rel_path) if rel_path else None

    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
            print(f"[FILE] Deleted {file_path}")
        except Exception as e:
            print(f"[ERROR] Failed to delete {file_path}: {e}")
    else:
        print(f"[SKIP] File not found: {file_path}")

    # Delete DB record
    cursor.execute("DELETE FROM docketwatch.dbo.documents WHERE doc_uid = ?", doc_uid)
    print(f"[DB] Deleted doc_uid: {doc_uid}")

conn.commit()
cursor.close()
conn.close()
print("\nDone.")
