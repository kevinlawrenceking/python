import os
import shutil
import pyodbc

# Setup
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

BASE_DIR = r"U:\docketwatch\docs"
CASES_DIR = os.path.join(BASE_DIR, "cases")

# Fetch all documents with rel_path
cursor.execute("SELECT doc_uid, rel_path FROM docketwatch.dbo.documents WHERE isfound = 0 OR isfound IS NULL")
rows = cursor.fetchall()

found_count = 0
moved_count = 0

for doc_uid, rel_path in rows:
    abs_path = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(abs_path):
        # File exists in correct location
        cursor.execute("UPDATE docketwatch.dbo.documents SET isfound = 1 WHERE doc_uid = ?", (doc_uid,))
        found_count += 1
    else:
        filename = os.path.basename(rel_path)
        misplaced_path = os.path.join(CASES_DIR, filename)

        if os.path.exists(misplaced_path):
            # File found in root of /cases, move it to correct folder
            correct_folder = os.path.join(CASES_DIR, os.path.dirname(rel_path).split("\\")[-1])
            os.makedirs(correct_folder, exist_ok=True)

            correct_path = os.path.join(BASE_DIR, rel_path)
            shutil.move(misplaced_path, correct_path)

            cursor.execute("UPDATE docketwatch.dbo.documents SET isfound = 1 WHERE doc_uid = ?", (doc_uid,))
            moved_count += 1
        # else: file is still missing

conn.commit()
print(f"Marked {found_count} documents as found.")
print(f"Moved {moved_count} documents into correct folders.")

cursor.close()
conn.close()
