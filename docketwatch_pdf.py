import os
import re
import uuid
import pyodbc
from datetime import datetime
from pdf2image import convert_from_path
import pytesseract
import shutil

# --- CONFIG ---
PDF_DIR = r"\\10.146.176.84\general\docketwatch\python\final_pdfs"
REMOVED_DIR = r"\\10.146.176.84\general\docketwatch\python\final_pdfs_removed"
POPPLER_PATH = r"C:\Poppler\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TOOL_ID = 26

# --- Set up Tesseract path ---
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
print("Python sees Tesseract at:", pytesseract.pytesseract.tesseract_cmd)
print("shutil.which('tesseract') returns:", shutil.which('tesseract'))
os.system('tesseract --version')

def get_db_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    return conn, conn.cursor()

def clean_ocr_text(text):
    if not text:
        return text
    text = text.replace('â€”', '—').replace('â€“', '–')
    text = text.replace('â€˜', "'").replace('â€™', "'")
    text = text.replace('â€œ', '"').replace('â€', '"')
    text = text.replace('Â°F', '°F').replace('Â', '')
    text = text.replace('â€¦', '...')
    text = re.sub(r'CoC mon YN Dn UU Se WY KY[\s\d|—]*', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()

def ocr_pdf(file_path):
    try:
        pages = convert_from_path(file_path, poppler_path=POPPLER_PATH)
        text = ""
        for page in pages:
            text += pytesseract.image_to_string(page) + "\n"
        return text.strip()
    except Exception as e:
        print(f"OCR failed for {file_path}: {e}")
        return None

def move_removed_pdfs():
    conn, cursor = get_db_cursor()
    files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf') and f.startswith('E')]
    moved = 0
    for fname in files:
        court_case_number = fname[1:-4]
        cursor.execute("""
            SELECT status FROM docketwatch.dbo.cases WHERE courtCaseNumber = ?
        """, (court_case_number,))
        row = cursor.fetchone()
        if row and row[0] == 'Removed':
            src = os.path.join(PDF_DIR, fname)
            dst = os.path.join(REMOVED_DIR, fname)
            print(f"Moving removed PDF: {fname}")
            shutil.move(src, dst)
            moved += 1
    cursor.close()
    conn.close()
    print(f"Moved {moved} removed PDFs.")

# Run before main
move_removed_pdfs()

def main():
    files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf') and f.startswith('E')]
    print(f"Found {len(files)} PDF files.")
    conn, cursor = get_db_cursor()
    inserted = 0

    for fname in files:
        court_case_number = fname[1:-4]
        cursor.execute("""
            SELECT id FROM docketwatch.dbo.cases 
            WHERE courtCaseNumber = ? AND status <> 'Removed'
        """, (court_case_number,))
        row = cursor.fetchone()
        if not row:
            print(f"Case not found in DB for courtCaseNumber {court_case_number} (file {fname}), skipping.")
            continue

        fk_case = row[0]
        rel_path = f"cases\\{fk_case}\\{fname}"

        cursor.execute("""
            SELECT COUNT(*) FROM docketwatch.dbo.documents
            WHERE rel_path = ?
        """, (rel_path,))
        if cursor.fetchone()[0] > 0:
            print(f"Skipped (already inserted): case {fk_case}, file {fname}")
            continue

        file_path = os.path.join(PDF_DIR, fname)
        if not os.path.exists(file_path):
            print(f"Missing file: {file_path}")
            continue

        file_size = os.path.getsize(file_path)
        date_downloaded = datetime.fromtimestamp(os.path.getmtime(file_path))

        print(f"OCR: {fname} ...")
        ocr_text = ocr_pdf(file_path)
        ocr_text = clean_ocr_text(ocr_text)
        ocr_text = str(ocr_text) if ocr_text else None
        ocr_text_raw = ocr_text

        doc_uid = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO docketwatch.dbo.documents
                (doc_uid,
                 fk_case,
                 fk_tool,
                 doc_id,
                 rel_path,
                 file_name,
                 file_size,
                 total_pages,
                 date_downloaded,
                 pdf_title,
                 pdf_no,
                 ocr_text_raw,
                 ocr_text,
                 summary_ai,
                 summary_ai_html,
                 is_storyworthy,
                 ai_processed_at)
            VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, NULL, NULL, ?, ?, NULL, NULL, NULL, NULL)
        """, (
            doc_uid,
            fk_case,
            TOOL_ID,
            rel_path,
            fname,
            file_size,
            date_downloaded,
            ocr_text_raw,
            ocr_text
        ))
        conn.commit()
        inserted += 1
        print(f"Inserted {fname} (courtCaseNumber {court_case_number})")

    print(f"Done. {inserted} new document(s) inserted.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
