import os
import re
import sys
import json
import cv2
import numpy as np
import pyodbc
import PyPDF2
import pytesseract
import markdown2
from bs4 import BeautifulSoup
from datetime import datetime
from pdf2image import convert_from_path
from cleantext import clean as clean_unicode
from scraper_base import log_message
import unicodedata
import google.generativeai as genai

# Configuration
DSN = "Docketwatch"
POPPLER_PATH = r"C:\\Poppler\\bin"
TESSERACT_PATH = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
MODEL_NAME = "gemini-2.5-pro"
RULES = r"""
SYSTEM: You are an experienced legal journalist. Your task is to analyze the following court document and produce a concise, neutral summary for a general audience.

Your analysis must adhere to these rules:
- Source Material: Base your summary only on the content of the provided document. Do not infer or include external information.
- Case Context: You will be provided with a short case summary to help anchor your understanding. However, your analysis must still focus exclusively on the content of the current document.
- Tone: Use plain, accessible English. Remain objective and avoid speculation. Write as if for an internal newsroom memo, not for public publication.
- Constraint: Do not describe the general case status or procedural history unless a specific, new event (like a scheduled hearing date or recent ruling) is explicitly mentioned in this document.

Follow this output format precisely:

### EVENT SUMMARY
Summarize the core filing, argument, or ruling in under 150 words.

### NEWSWORTHINESS
- Purpose: Evaluate whether the content of this specific document alone justifies its own story.
- Output:  
  Yes - <reason in 15 words or less>  
  OR  
  No - <reason in 15 words or less>

### STORY
- If NEWSWORTHINESS is "No":
  - HEADLINE: No Story Necessary.
  - SUBHEAD:
  - BODY:
- If NEWSWORTHINESS is "Yes":
  - HEADLINE: <A Title-Case Headline in 15 Words or Less>
  - SUBHEAD: <A descriptive sentence-case subhead in 25 words or less>
  - BODY: <A 250–400 word article using the markdown headings below>

### KEY DETAILS
Write the key facts in this section. Do not include instructions or placeholder text.

### WHAT'S NEXT
List any next steps or dates found in the document. Do not include instructions or placeholder text.

Only return the finished article — do not echo this prompt.

Begin.

### CASE OVERVIEW
The following is a high-level case summary to help you contextualize the document:

{CASE_OVERVIEW}

### EVENT
Date: {event_date}  
Description: {event_desc}

### DOCUMENT TEXT
{PDF_BODY}

--- END OF DOCUMENT ---
"""



# Utility Functions
def get_cursor():
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn, conn.cursor()

def get_util(cur, col):
    cur.execute(f"SELECT {col} FROM docketwatch.dbo.utilities")
    row = cur.fetchone()
    return row[0] if row else None

def fix_encoding_garbage(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def normalize_quotes(text):
    return unicodedata.normalize('NFKD', text).replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")

def preprocess(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 5, 75, 75)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    bw = cv2.dilate(bw, kernel, iterations=1)
    bw = cv2.erode(bw, kernel, iterations=1)
    coords = np.column_stack(np.where(bw > 0))
    if coords.size == 0:
        return bw
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 1.5:
        return bw
    M = cv2.getRotationMatrix2D((bw.shape[1] / 2, bw.shape[0] / 2), angle, 1.0)
    return cv2.warpAffine(bw, M, (bw.shape[1], bw.shape[0]), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def tesseract_page(img):
    txt = pytesseract.image_to_string(img, config="--oem 1 --psm 6")
    return txt

def pdf_to_text(path):
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for pg in reader.pages:
                text += (pg.extract_text() or "") + "\n"
    except Exception:
        pass
    if len(text.strip()) >= 200:
        return text
    pages = convert_from_path(path, dpi=300, poppler_path=POPPLER_PATH)
    for pil in pages:
        img = preprocess(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
        text += tesseract_page(img) + "\n"
    return text

def clean_ocr_text(txt):
    txt = re.sub(r'^Page \d+\s*\n', '', txt, flags=re.MULTILINE)
    txt = re.sub(r'-\n(?=\w)', '', txt)
    txt = re.sub(r'(?<!\n)\n(?!\n)', ' ', txt)
    txt = re.sub(r' +', ' ', txt)
    txt = clean_unicode(txt, fix_unicode=True)
    return normalize_quotes(txt.strip())

def refine_ocr_with_ai(text: str, api_key: str) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
SYSTEM: You are an expert legal document cleaner.
Your job is to correct OCR errors in legal text while preserving original meaning.
Fix split words, misspellings, and remove junk characters.

--- TEXT TO CLEAN ---
{text[:9000]}
--- END ---

Return only the corrected text. Do not summarize or explain.
"""
    response = model.generate_content(prompt)
    return response.candidates[0].content.parts[0].text.strip()

def ask_gemini(case_summary, event_desc, event_date, pdf_text, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # Ensure input size is controlled
    case_summary = (case_summary or "")[:2000]  # #2: Increased limit to preserve case detail
    event_desc = (event_desc or "")[:500]

    # Build the body content with event info and PDF text
    body_text = f"Date: {event_date}\nDescription: {event_desc}\n\n{pdf_text}"
    if len(body_text) > 10000:
        body_text = body_text[:8000] + "\n...\n" + body_text[-2000:]

    # Replace both placeholders in the rules template
    full_prompt = RULES.replace("{CASE_OVERVIEW}", case_summary).replace("{PDF_BODY}", body_text)

    # Optional debug output (commented out for now)
    # print("========== GEMINI PROMPT START ==========")
    # print(full_prompt[:16000])
    # print("=========== GEMINI PROMPT END ===========")

    # Submit to Gemini and return result
    response = model.generate_content(full_prompt[:16000])
    return response.text.strip()


def process_single_pdf(doc_uid: str):
    conn, cur = get_cursor()
    key = get_util(cur, "gemini_api")
    docs_root = get_util(cur, "docs_root")
    if not (key and docs_root):
        print("Missing Gemini key or docs_root.")
        return

    cur.execute("""
SELECT 
    c.summarize,
    ISNULL(e.event_description, p.pdf_title) AS event_description,
    CONVERT(char(10), ISNULL(e.event_date, p.date_downloaded), 23) AS event_date,
    p.ocr_text,
    p.fk_case
FROM docketwatch.dbo.documents p
LEFT JOIN docketwatch.dbo.case_events e ON e.id = p.fk_case_event
JOIN docketwatch.dbo.cases c ON c.id = p.fk_case
WHERE p.doc_uid = ?
    """, doc_uid)
    row = cur.fetchone()
    if not row:
        print("PDF id not found.")
        return

    summ, ev_desc, ev_date, ocr_text, case_id = row
    cur.execute("""
        SELECT TOP 1 rel_path
        FROM docketwatch.dbo.documents
        WHERE fk_case = ?
        ORDER BY date_downloaded DESC
    """, case_id)
    rel_row = cur.fetchone()
    abs_path = os.path.join(docs_root, rel_row[0]) if rel_row else None

    if (not ocr_text or len(ocr_text.strip()) < 100) and abs_path and os.path.isfile(abs_path):
        raw = pdf_to_text(abs_path)
        clean = clean_ocr_text(raw)
        try:
            clean = refine_ocr_with_ai(clean, key)
        except Exception as e:
            log_message(cur, None, "WARNING", f"Refinement failed for {doc_uid}: {e}")
        cur.execute("""
            UPDATE docketwatch.dbo.documents
            SET ocr_text_raw = ?, ocr_text = ?, ai_processed_at = ?
            WHERE doc_uid = CAST(? AS uniqueidentifier)
        """, (raw, clean, datetime.now(), doc_uid))
        conn.commit()
        ocr_text = clean

    pdf_text = clean_ocr_text(ocr_text or "")
    if len(pdf_text.strip()) < 100:
        print("Skipping Gemini summary — OCR result is too poor.")
        return

    try:
        gem = ask_gemini(summ or "", ev_desc or "", ev_date or "", pdf_text, key)
        gem = fix_encoding_garbage(gem)
        gem = normalize_quotes(gem)
        html = BeautifulSoup(markdown2.markdown(gem), "html.parser").prettify()
    except Exception as e:
        log_message(cur, None, "ERROR", f"Gemini fail {doc_uid}: {e}")
        return

    cur.execute("""
        UPDATE docketwatch.dbo.documents
        SET summary_ai = ?, summary_ai_html = ?, ai_processed_at = ?
        WHERE doc_uid = CAST(? AS uniqueidentifier)
    """, (gem, html, datetime.now(), doc_uid))
    conn.commit()
    log_message(cur, None, "INFO", f"PDF {doc_uid} processed")
    cur.close(); conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pacer_case_event_pdf_summarizer.py <doc_uid>")
    else:
        process_single_pdf(sys.argv[1])
