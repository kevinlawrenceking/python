import os
import re
import uuid
import pyodbc
from datetime import datetime
from pdf2image import convert_from_path
import pytesseract
import shutil

# --- CONFIG ---
BASE_DIR = r"\\10.146.176.84\general\docketwatch\cases"
POPPLER_PATH = r"C:\Poppler\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TOOL_ID = 26

# --- Set up Tesseract path ---
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

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
    text = re.sub(r'\n{3,}', '\n\n', text)
    return '\n'.join(line.rstrip() for line in text.splitlines()).strip()

def ocr_pdf(file_path):
    try:
        pages = convert_from_path(file_path, poppler_path=POPPLER_PATH)
        return "\n".join(pytesseract.image_to_string(page) for page in pages).strip()
    except Exception as e:
        print(f"OCR failed for {file_path}: {e}")
        return None

def main():
    conn, cursor = get_db_cursor()

    cursor.execute("""
        SELECT id, courtCaseNumber
        FROM docketwatch.dbo.cases
        WHERE courtCaseNumber IS NOT NULL AND status <> 'Removed' AND fk_tool = ?
    """, (TOOL_ID,))
    cases = cursor.fetchall()

    inserted = 0
    for fk_case, court_case_number in cases:
        fname = f"E{court_case_number}.pdf"
        rel_path = f"cases\\{fk_case}\\{fname}"
        abs_path = os.path.join(BASE_DIR, str(fk_case), fname)

        if not os.path.exists(abs_path):
            continue

        cursor.execute("SELECT COUNT(*) FROM docketwatch.dbo.documents WHERE rel_path = ?", (rel_path,))
        if cursor.fetchone()[0] > 0:
            continue

        file_size = os.path.getsize(abs_path)
        date_downloaded = datetime.fromtimestamp(os.path.getmtime(abs_path))

        print(f"OCR: {fname} ...")
        ocr_text = clean_ocr_text(ocr_pdf(abs_path) or "")
        doc_uid = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO docketwatch.dbo.documents (
                doc_uid, fk_case, fk_tool, doc_id, rel_path, file_name,
                file_size, total_pages, date_downloaded, pdf_title, pdf_no,
                ocr_text_raw, ocr_text, summary_ai, summary_ai_html, is_storyworthy, ai_processed_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, NULL, NULL, ?, ?, NULL, NULL, NULL, NULL)
        """, (
            doc_uid, fk_case, TOOL_ID, rel_path, fname, file_size, date_downloaded,
            ocr_text, ocr_text
        ))
        conn.commit()
        inserted += 1
        print(f"Inserted {fname} → {rel_path}")

    cursor.close()
    conn.close()
    print(f"Done. {inserted} document(s) inserted.")

if __name__ == "__main__":
    main()
