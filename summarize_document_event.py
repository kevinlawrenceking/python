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
from scraper_base import log_message, setup_logging
import unicodedata
import google.generativeai as genai
from summary_parser import parse_ai_summary, save_structured_summary

# Configuration
DSN = "Docketwatch"
POPPLER_PATH = r"C:\\Poppler\\bin"
TESSERACT_PATH = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
MODEL_NAME = "gemini-1.5-flash"
RULES = r"""
SYSTEM: You are a senior legal journalist at a major entertainment news organization. Your task is to analyze court documents and create precise, actionable summaries for reporters covering celebrity cases, high-profile litigation, and entertainment industry legal matters.

CRITICAL REQUIREMENTS:
1. STRICT FORMAT: You must follow the exact HTML format specified below. Any deviation will be rejected.
2. CONTENT FOCUS: Base analysis ONLY on the provided document content. Never infer or add external information.
3. REPORTER PERSPECTIVE: Write for journalists who need to quickly understand what happened and why it matters.
4. PRECISION: Be specific with names, dates, amounts, and legal terms. Avoid generalizations.

OUTPUT FORMAT (MANDATORY):
<h3>EVENT SUMMARY</h3>
<p>[In exactly 2-3 sentences, describe what happened in this specific document. Include who filed what, when, and the core request/ruling/argument. Maximum 100 words.]</p>

<h3>NEWSWORTHINESS</h3>
<p>[Evaluate this specific document's news value]</p>
<p>Yes - [Specific reason why this deserves coverage: new allegations, major ruling, celebrity involvement, significant monetary amount, unusual legal strategy, etc.]</p>
<p>OR</p>
<p>No - [Specific reason why this is routine: procedural filing, standard motion, administrative update, etc.]</p>

<h3>STORY</h3>
<ul>
<li>HEADLINE: [If newsworthy: Active, specific headline under 12 words. If not newsworthy: "No Story Necessary."]</li>
<li>SUBHEAD: [If newsworthy: Context/impact in under 20 words. If not newsworthy: leave blank.]</li>
<li>BODY: [If newsworthy: 200-300 word article with key quotes, context, and implications. If not newsworthy: leave blank.]</li>
</ul>

<h3>KEY DETAILS</h3>
<ul>
<li>[Bullet point list of 3-5 most important facts from this document]</li>
<li>[Include specific names, amounts, deadlines, and legal terminology]</li>
<li>[Focus on actionable information for reporters]</li>
</ul>

<h3>WHAT'S NEXT</h3>
<p>[Any upcoming deadlines, hearing dates, or required responses mentioned in the document. If none specified, state "No specific next steps mentioned in this document."]</p>

NEWSWORTHINESS GUIDELINES:
- YES if: Celebrity/public figure involved, significant money at stake (>$1M), criminal charges, major corporate disputes, precedent-setting legal issues, scandal allegations, injunctions/restraining orders
- NO if: Routine procedural motions, standard attorney changes, discovery requests, scheduling orders, administrative updates

QUALITY STANDARDS:
- Use proper names and titles exactly as they appear
- Include specific dollar amounts, percentages, and dates
- Distinguish between requests and actual rulings
- Highlight any unusual or aggressive legal strategies
- Note any mentions of public figures, celebrities, or major corporations

ERROR HANDLING:
- If document is corrupted/unreadable: State "Document appears corrupted or unreadable"
- If document lacks substance: Focus on what little content exists
- If document is purely procedural: Acknowledge but keep analysis brief

Begin analysis:

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
    # Setup logging with the script filename
    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")
    
    conn, cur = get_cursor()
    log_message(cur, None, "INFO", f"Starting PDF processing for doc_uid: {doc_uid}")
    
    key = get_util(cur, "gemini_api")
    docs_root = get_util(cur, "docs_root")
    if not (key and docs_root):
        log_message(cur, None, "ERROR", "Missing Gemini key or docs_root configuration")
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
        log_message(cur, None, "ERROR", f"PDF document not found for doc_uid: {doc_uid}")
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
        log_message(cur, None, "INFO", f"Extracting OCR text from PDF: {abs_path}")
        raw = pdf_to_text(abs_path)
        clean = clean_ocr_text(raw)
        try:
            clean = refine_ocr_with_ai(clean, key)
            log_message(cur, None, "INFO", f"OCR text refined with AI for {doc_uid}")
        except Exception as e:
            log_message(cur, None, "WARNING", f"Refinement failed for {doc_uid}: {e}")
        cur.execute("""
            UPDATE docketwatch.dbo.documents
            SET ocr_text_raw = ?, ocr_text = ?, ai_processed_at = ?
            WHERE doc_uid = CAST(? AS uniqueidentifier)
        """, (raw, clean, datetime.now(), doc_uid))
        conn.commit()
        log_message(cur, None, "INFO", f"OCR text updated in database for {doc_uid}")
        ocr_text = clean

    pdf_text = clean_ocr_text(ocr_text or "")
    if len(pdf_text.strip()) < 100:
        log_message(cur, None, "WARNING", f"Skipping Gemini summary for {doc_uid} - OCR result too poor (length: {len(pdf_text.strip())})")
        print("Skipping Gemini summary — OCR result is too poor.")
        return

    try:
        log_message(cur, None, "INFO", f"Requesting Gemini summary for {doc_uid}")
        gem = ask_gemini(summ or "", ev_desc or "", ev_date or "", pdf_text, key)
        gem = fix_encoding_garbage(gem)
        gem = normalize_quotes(gem)
        html = BeautifulSoup(markdown2.markdown(gem), "html.parser").prettify()
        log_message(cur, None, "INFO", f"Gemini summary generated successfully for {doc_uid}")
        
        # Parse the structured AI summary
        parsed_summary = parse_ai_summary(gem)
        
    except Exception as e:
        log_message(cur, None, "ERROR", f"Gemini fail {doc_uid}: {e}")
        return

    # Save both the original summary and structured data
    cur.execute("""
        UPDATE docketwatch.dbo.documents
        SET summary_ai = ?, summary_ai_html = ?, ai_processed_at = ?
        WHERE doc_uid = CAST(? AS uniqueidentifier)
    """, (gem, html, datetime.now(), doc_uid))
    
    # Save structured summary components
    try:
        save_structured_summary(cur, doc_uid, parsed_summary)
        log_message(cur, None, "INFO", f"PDF {doc_uid} processed with structured data")
    except Exception as e:
        log_message(cur, None, "WARNING", f"Failed to save structured data for {doc_uid}: {e}")
        log_message(cur, None, "INFO", f"PDF {doc_uid} processed (summary only)")
    
    conn.commit()
    cur.close(); conn.close()

def get_default_doc_uid():
    """Get the latest document that needs summarization."""
    conn, cur = get_cursor()
    try:
        cur.execute("""
            SELECT doc_uid AS default_doc_uid 
            FROM docketwatch.dbo.documents 
            WHERE pdf_type <> 'Filing' AND summary_ai IS NULL AND fk_tool = 2 AND pdf_url IS NOT NULL
            ORDER BY date_downloaded DESC
        """)
        row = cur.fetchone()
        return row.default_doc_uid if row else None
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # No argument supplied, find the default document to process
        default_doc_uid = get_default_doc_uid()
        if default_doc_uid:
            print(f"No doc_uid argument supplied. Processing latest unsummarized document: {default_doc_uid}")
            process_single_pdf(default_doc_uid)
        else:
            print("No unsummarized documents found.")
            print("Usage: python summarize_document_event.py <doc_uid>")
    else:
        process_single_pdf(sys.argv[1])
