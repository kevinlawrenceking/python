import os
import pyodbc

# Directory where all case folders live
ROOT_DIR = r"\\10.146.176.84\general\docketwatch\docs\cases"
DSN = "Docketwatch"

def get_all_document_rel_paths():
    """Fetch all rel_path entries from the documents table."""
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rel_path
        FROM docketwatch.dbo.documents
        WHERE rel_path IS NOT NULL
    """)
    db_paths = {row.rel_path.lower() for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return db_paths

def get_all_pdf_files(root_dir):
    """Walk the filesystem and collect all PDF files with 'cases\\' prefix."""
    all_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                rel_path = f"cases\\{os.path.relpath(os.path.join(root, file), start=ROOT_DIR)}"
                rel_path = rel_path.replace("/", "\\").lower()
                all_files.append(rel_path)
    return all_files

def main():
    db_paths = get_all_document_rel_paths()
    file_paths = get_all_pdf_files(ROOT_DIR)

    extras = [f for f in file_paths if f not in db_paths]

    print(f"\n[!] Found {len(extras)} extra PDF file(s) not in database:\n")
    for f in extras:
        print(f"  - {f}")

if __name__ == "__main__":
    main()
