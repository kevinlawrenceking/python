import os
import pyodbc

# Configuration
ROOT_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"
DSN = "Docketwatch"

# Connect to DB
conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
cursor = conn.cursor()

# Query all documents with rel_path and doc_id
cursor.execute("""
    SELECT doc_uid, rel_path, fk_case, doc_id
    FROM docketwatch.dbo.documents
    WHERE rel_path IS NOT NULL AND doc_id IS NOT NULL
""")
rows = cursor.fetchall()

for doc_uid, rel_path, fk_case, doc_id in rows:
    filename = os.path.basename(rel_path)
    if not filename.lower().startswith("e"):
        expected_filename = f"E{doc_id}.pdf"
        new_rel_path = f"cases\\{fk_case}\\{expected_filename}"
        old_path = os.path.join(ROOT_DIR, str(fk_case), filename)
        new_path = os.path.join(ROOT_DIR, str(fk_case), expected_filename)

        # Rename file on disk
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)
                print(f"Renamed: {old_path} → {new_path}")
            except Exception as e:
                print(f"Failed to rename {old_path}: {e}")
                continue

        # Update rel_path in database
        cursor.execute("""
            UPDATE docketwatch.dbo.documents
            SET rel_path = ?
            WHERE doc_uid = ?
        """, (new_rel_path, doc_uid))

conn.commit()
cursor.close()
conn.close()
print("Done.")
