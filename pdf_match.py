import os
import pyodbc

FINAL_PDF_DIR = r"\\10.146.176.84\general\mediaroot\pacer_pdfs"

# --- Connect to DB ---
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# --- Get all expected PDF filenames from documents table ---
cursor.execute("""
    SELECT doc_id
    FROM docketwatch.dbo.documents
    WHERE rel_path IS NOT NULL AND doc_id IS NOT NULL
""")

# Construct expected filenames: E{doc_id}.pdf
db_files = set(f"E{str(row.doc_id).strip()}.pdf" for row in cursor.fetchall() if row.doc_id)

# --- Get all actual files in directory ---
disk_files = set(f for f in os.listdir(FINAL_PDF_DIR) if f.lower().endswith(".pdf"))

# --- Compare ---
missing_on_disk = db_files - disk_files
extra_on_disk = disk_files - db_files

print("\n=== Validation Report ===\n")
print(f"✔ Files expected in DB: {len(db_files)}")
print(f"✔ Files found on disk: {len(disk_files)}\n")

if missing_on_disk:
    print(f" Missing on Disk ({len(missing_on_disk)}):")
    for f in sorted(missing_on_disk):
        print(f"  - {f}")
else:
    print(" All expected files from DB are present on disk.")

if extra_on_disk:
    print(f"\n⚠ Extra on Disk ({len(extra_on_disk)}):")
    for f in sorted(extra_on_disk):
        print(f"  - {f}")
else:
    print("\nNo extra files on disk.")

# Cleanup
cursor.close()
conn.close()
