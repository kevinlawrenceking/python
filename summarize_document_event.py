import os
import re
import sys
import json
import time
from typing import Any, Dict, List, Optional, Tuple
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
import logging


FACT_GUARD = os.getenv("FACT_GUARD", "true").strip().lower() == "true"

# Configuration
DSN = "Docketwatch"
POPPLER_PATH = r"C:\\Poppler\\bin"
TESSERACT_PATH = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
# Model selection handled dynamically by get_available_model() - optimized for moderate volume
FAST_OCR_DPI = 200          # First-pass DPI for scanned docs
HIGH_QUALITY_OCR_DPI = 300  # Escalation DPI only if needed
OCR_TEXT_THRESHOLD = 200    # If below this after fast OCR, escalate
EARLY_EXIT_TEXT_THRESHOLD = 1200  # Stop OCR early once enough text captured
CACHED_MODEL_NAME = None    # Cache selected model to avoid repeated list_models calls
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


HARD_RULES_PREFACE = """Hard rules:
- Use only the provided inputs.
- If not explicitly present, mark unknown or leave blank.
- Never invent names, dates, counts, plea status, or outcomes.
- If unsure, choose the conservative option and state "unknown".
"""

PRO_SUMMARY_GUIDANCE = """Professional guidance:
- Attribute actions to the document, not the broader case, unless the document states it.
- Separate requests from rulings: use "seeks" or "asks" unless the order grants or denies relief.
- Prefer concrete nouns and numbers; avoid adjectives.
- Keep the first sentence under 30 words and avoid passive voice that hides the actor.
- For criminal matters, do not imply plea or verdict unless the document clearly states it—quote the operative phrase when present.
- For judgments, list confinement, supervision, fines, restitution, and forfeiture as separate bullets.
"""

EXTRACTION_PROMPT_TEMPLATE = (
    "{hard_rules}\n"
    "Role: You extract structured facts from legal documents for newsroom use. You must not infer."
    " Only include facts explicitly present in the provided text. If unknown, write \"unknown\" or [].\n\n"
    "Return JSON only. No prose. Your response must match this exact schema (all keys required):\n"
    "{\n"
    "  \"doc_type\": \"unknown\",\n"
    "  \"filing_date_iso\": \"unknown\",\n"
    "  \"parties\": {\n"
    "    \"plaintiff\": \"unknown\",\n"
    "    \"defendant\": \"unknown\",\n"
    "    \"others\": []\n"
    "  },\n"
    "  \"filing_action_summary\": \"unknown\",\n"
    "  \"requested_relief\": [],\n"
    "  \"court_status\": \"unknown\",\n"
    "  \"orders\": [],\n"
    "  \"special_conditions\": [],\n"
    "  \"financial_terms\": [],\n"
    "  \"statutes\": [],\n"
    "  \"counts_alleged\": [],\n"
    "  \"counts_convicted\": [],\n"
    "  \"counts_dismissed\": [],\n"
    "  \"hearing_schedule\": [],\n"
    "  \"next_actions\": [],\n"
    "  \"newsworthiness\": \"unknown\",\n"
    "  \"newsworthiness_reason\": \"unknown\",\n"
    "  \"adjudication_mode\": \"unknown\",\n"
    "  \"sentence\": {\n"
    "    \"imprisonment_months\": 0,\n"
    "    \"supervised_release_years\": 0,\n"
    "    \"fine_usd\": 0,\n"
    "    \"restitution_usd\": 0\n"
    "  },\n"
    "  \"protective_terms\": [],\n"
    "  \"verbatim_support\": [],\n"
    "  \"confidence\": \"low\"\n"
    "}\n\n"
    "Instructions:\n"
    "- Populate text fields with concise summaries drawn verbatim or paraphrased directly from the document.\n"
    "- Use ISO format (YYYY-MM-DD) for dates when provided.\n"
    "- For lists, provide each discrete request, order, hearing, or financial term as a separate string.\n"
    "- For every field you populate with more than \"unknown\" or an empty list, add an object to verbatim_support with keys \"field\" and \"quote\" holding the supporting snippet.\n"
    "- If a field truly has no information, leave it as \"unknown\" or []. Do not invent values.\n\n"
    "Document context:\n"
    "- Case overview: {case_overview}\n"
    "- Event date: {event_date}\n"
    "- Event description: {event_desc}\n\n"
    "Document text:\n"
    "{pdf_body}\n"
)

SUMMARY_PROMPT_TEMPLATE = (
    "{hard_rules}\n{professional_guidance}\n"
    "Role: Senior legal journalist. Write a concise, factual brief for reporters. Use only the provided structured JSON."
    " Do not add or guess. Prioritize filing_action_summary, requested_relief, court_status, orders, financial_terms, statutes, and sentence details.\n\n"
    "You will receive a single JSON object named DATA. You must write the HTML sections exactly as specified."
    " If DATA lacks details, state \"No specific information in this document\" where needed.\n\n"
    "DATA:\n{extraction_json}\n\n"
    "Output format (mandatory and exact):\n"
    "<h3>EVENT SUMMARY</h3>\n"
    "<p>[2-3 sentences using only DATA]</p>\n\n"
    "<h3>NEWSWORTHINESS</h3>\n"
    "<p>[Yes or No based on DATA.newsworthiness] - [One sentence reason from DATA.newsworthiness_reason]</p>\n\n"
    "<h3>STORY</h3>\n"
    "<ul>\n"
    "<li>HEADLINE: [If newsworthy: under 12 words. Else: No Story Necessary.]</li>\n"
    "<li>SUBHEAD: [If newsworthy: under 20 words. Else: ]</li>\n"
    "<li>BODY: [If newsworthy: 200-300 words drawing only from DATA. Else: ]</li>\n"
    "</ul>\n\n"
    "<h3>KEY DETAILS</h3>\n"
    "<ul>\n"
    "<li>[3-5 bullets from DATA. Use parties, requested_relief, orders, financial_terms, statutes, counts, sentence, protective_terms]</li>\n"
    "</ul>\n\n"
    "<h3>WHAT'S NEXT</h3>\n"
    "<p>[From DATA.next_actions or \"No specific next steps mentioned in this document.\"]</p>\n"
)

VERIFIER_PROMPT_TEMPLATE = (
    "{hard_rules}\n"
    "Role: Managing editor. Task: check the HTML summary for unsupported or contradictory claims. Use only DATA.\n\n"
    "Rules:\n"
    "- Any claim in the summary must be directly supported by DATA fields.\n"
    "- Disallow claims about pleas, verdicts, guilt, innocence, sex trafficking, racketeering, dollar amounts, sentence terms, or contact bans unless present in DATA.\n"
    "- Disallow verbs that imply outcomes (granted, denied, admitted, confessed, pleaded) unless DATA supports them.\n"
    "- If any violation exists, return \"FAILED\" and list each offending sentence with the missing DATA fields.\n"
    "- If fully supported, return \"PASSED\".\n\n"
    "DATA:\n{extraction_json}\n\n"
    "SUMMARY_HTML:\n{summary_html}\n\n"
    "Return strictly one of:\nPASSED\nor\nFAILED: <bullet list of issues>\n"
)


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
    """Extract text quickly; escalate quality only if needed.

    Strategy:
    1. Try native PDF text extraction (PyPDF2) - very fast.
    2. If insufficient (< OCR_TEXT_THRESHOLD), run fast OCR at lower DPI.
    3. If still insufficient, escalate to high DPI only until enough text gathered.
    4. Early exit once EARLY_EXIT_TEXT_THRESHOLD reached to avoid wasting time.
    """
    # 1. Native text extraction
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for pg in reader.pages:
                extracted = pg.extract_text() or ""
                if extracted:
                    text += extracted + "\n"
        if len(text.strip()) >= OCR_TEXT_THRESHOLD:
            return text
    except Exception:
        pass

    # 2. Fast low-DPI OCR
    try:
        pages = convert_from_path(path, dpi=FAST_OCR_DPI, poppler_path=POPPLER_PATH)
    except Exception as e:
        _simple_log(f"Fast OCR conversion failed: {e}", "WARNING")
        return text  # Return whatever we have (may be empty)

    ocr_text = ""
    for idx, pil in enumerate(pages, start=1):
        img = preprocess(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
        ocr_text += tesseract_page(img) + "\n"
        if len(ocr_text) >= EARLY_EXIT_TEXT_THRESHOLD:
            break

    if len(ocr_text.strip()) >= OCR_TEXT_THRESHOLD:
        return ocr_text

    # 3. Escalate selectively (high DPI) only if still too little text
    try:
        pages_hq = convert_from_path(path, dpi=HIGH_QUALITY_OCR_DPI, poppler_path=POPPLER_PATH)
    except Exception as e:
        _simple_log(f"High-quality OCR conversion failed: {e}", "WARNING")
        return ocr_text or text

    for idx, pil in enumerate(pages_hq, start=1):
        img = preprocess(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
        ocr_text += tesseract_page(img) + "\n"
        if len(ocr_text) >= EARLY_EXIT_TEXT_THRESHOLD:
            break
    return ocr_text or text

def clean_ocr_text(txt):
    txt = re.sub(r'^Page \d+\s*\n', '', txt, flags=re.MULTILINE)
    txt = re.sub(r'-\n(?=\w)', '', txt)
    txt = re.sub(r'(?<!\n)\n(?!\n)', ' ', txt)
    txt = re.sub(r' +', ' ', txt)
    txt = clean_unicode(txt, fix_unicode=True)
    return normalize_quotes(txt.strip())

def _simple_log(message: str, level: str = "INFO"):
    """Wrapper to safely log without requiring DB cursor/task context."""
    try:
        # Supply None for cursor and fk_task_run so base function just standard-logs
        log_message(None, None, level, message)
    except TypeError:
        # Fallback if signature changes elsewhere
        if level == "ERROR":
            logging.error(message)
        elif level == "WARNING":
            logging.warning(message)
        else:
            logging.info(message)


def get_available_model(api_key: str) -> str:
    """Return the single approved Gemini model for summaries."""
    global CACHED_MODEL_NAME
    if not CACHED_MODEL_NAME:
        CACHED_MODEL_NAME = "gemini-2.5-pro"
    # Ensure client is configured for completeness
    genai.configure(api_key=api_key)
    return CACHED_MODEL_NAME


def _response_to_text(response: Any) -> str:
    if hasattr(response, "text") and response.text:
        return response.text.strip()
    if hasattr(response, "candidates") and response.candidates:
        parts = response.candidates[0].content.parts if response.candidates[0].content else []
        texts = [getattr(part, "text", "") for part in parts]
        combined = "".join(texts).strip()
        if combined:
            return combined
    raise ValueError("LLM response did not contain text content")


def unwrap_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        body = stripped[3:]
        # Drop optional language hint on the same line
        if "\n" in body:
            body = body.split("\n", 1)[1]
        else:
            body = ""
        if body.endswith("```"):
            body = body[:-3]
        stripped = body.strip()
    return stripped


def ensure_extraction_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    def _clean_str(val: Any, default: str = "unknown") -> str:
        if val is None:
            return default
        if isinstance(val, str):
            val = val.strip()
            return val if val else default
        return str(val).strip() or default

    def _clean_list(val: Any) -> List[Any]:
        if isinstance(val, list):
            return val
        if val in (None, ""):
            return []
        return [val]

    def _clean_int_list(val: Any) -> List[int]:
        result: List[int] = []
        for item in _clean_list(val):
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result

    normalized: Dict[str, Any] = {}
    normalized["doc_type"] = _clean_str(data.get("doc_type")).lower()
    normalized["filing_date_iso"] = _clean_str(data.get("filing_date_iso"))

    parties = data.get("parties") or {}
    normalized["parties"] = {
        "plaintiff": _clean_str(parties.get("plaintiff"), "unknown"),
        "defendant": _clean_str(parties.get("defendant"), "unknown"),
        "others": [str(p).strip() for p in parties.get("others", []) if str(p).strip()],
    }

    normalized["filing_action_summary"] = _clean_str(data.get("filing_action_summary"))
    normalized["requested_relief"] = [str(item).strip() for item in _clean_list(data.get("requested_relief")) if str(item).strip()]
    normalized["court_status"] = _clean_str(data.get("court_status"))
    normalized["counts_convicted"] = _clean_int_list(data.get("counts_convicted"))
    normalized["counts_dismissed"] = _clean_int_list(data.get("counts_dismissed"))
    normalized["counts_alleged"] = _clean_int_list(data.get("counts_alleged"))
    normalized["statutes"] = [str(s).strip() for s in _clean_list(data.get("statutes")) if str(s).strip()]
    normalized["adjudication_mode"] = _clean_str(data.get("adjudication_mode"), "unknown").lower()

    sentence = data.get("sentence") or {}
    normalized["sentence"] = {
        "imprisonment_months": int(sentence.get("imprisonment_months") or 0),
        "supervised_release_years": int(sentence.get("supervised_release_years") or 0),
        "fine_usd": int(sentence.get("fine_usd") or 0),
        "restitution_usd": int(sentence.get("restitution_usd") or 0),
    }

    normalized["orders"] = [str(o).strip() for o in _clean_list(data.get("orders")) if str(o).strip()]
    normalized["special_conditions"] = [str(o).strip() for o in _clean_list(data.get("special_conditions")) if str(o).strip()]
    normalized["financial_terms"] = [str(o).strip() for o in _clean_list(data.get("financial_terms")) if str(o).strip()]
    normalized["hearing_schedule"] = [str(o).strip() for o in _clean_list(data.get("hearing_schedule")) if str(o).strip()]
    normalized["protective_terms"] = [str(o).strip() for o in _clean_list(data.get("protective_terms")) if str(o).strip()]
    normalized["next_actions"] = [str(o).strip() for o in _clean_list(data.get("next_actions")) if str(o).strip()]
    normalized["newsworthiness"] = _clean_str(data.get("newsworthiness"), "unknown").lower()
    normalized["newsworthiness_reason"] = _clean_str(data.get("newsworthiness_reason"), "unknown")

    support_entries = []
    for entry in _clean_list(data.get("verbatim_support")):
        if isinstance(entry, dict):
            field = _clean_str(entry.get("field"))
            quote = _clean_str(entry.get("quote"))
            support_entries.append({"field": field, "quote": quote})
    normalized["verbatim_support"] = support_entries

    normalized["confidence"] = _clean_str(data.get("confidence"), "low").lower()
    return normalized


def serialize_extraction(extraction: Dict[str, Any]) -> str:
    return json.dumps(extraction, ensure_ascii=False, sort_keys=True)


def extraction_has_substance(extraction: Dict[str, Any]) -> bool:
    string_keys = [
        "filing_action_summary",
        "court_status",
        "newsworthiness_reason",
        "adjudication_mode",
    ]
    list_keys = [
        "requested_relief",
        "orders",
        "special_conditions",
        "financial_terms",
        "hearing_schedule",
        "next_actions",
        "statutes",
        "counts_alleged",
        "counts_convicted",
        "counts_dismissed",
        "protective_terms",
    ]

    for key in string_keys:
        value = str(extraction.get(key) or "").strip().lower()
        if value and value != "unknown":
            return True

    for key in list_keys:
        items = extraction.get(key) or []
        if isinstance(items, list) and any(str(item).strip() for item in items):
            return True

    sentence = extraction.get("sentence") or {}
    if any((sentence.get("imprisonment_months") or 0, sentence.get("supervised_release_years") or 0,
            sentence.get("fine_usd") or 0, sentence.get("restitution_usd") or 0)):
        return True

    return False


def extract_facts(pdf_text: str, case_overview: str, event_desc: str, event_date: str, api_key: str) -> Tuple[str, Dict[str, Any]]:
    model = genai.GenerativeModel(get_available_model(api_key))
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        hard_rules=HARD_RULES_PREFACE,
        case_overview=case_overview or "unknown",
        event_date=event_date or "unknown",
        event_desc=event_desc or "unknown",
        pdf_body=pdf_text or ""
    )
    response = model.generate_content(prompt)
    raw_json = unwrap_code_fence(_response_to_text(response))
    if not raw_json.strip():
        raise ValueError("Extraction response was empty")
    trimmed = raw_json.strip()
    try:
        data = json.loads(trimmed)
    except json.JSONDecodeError as exc:
        repaired = trimmed
        changed = False
        if repaired and not repaired.startswith("{"):
            repaired = "{" + repaired
            changed = True
        if repaired and not repaired.endswith("}"):
            repaired = repaired + "}"
            changed = True
        if changed:
            try:
                data = json.loads(repaired)
                raw_json = repaired
            except json.JSONDecodeError:
                data = None
        else:
            data = None
        if data is None:
            preview = trimmed.replace("\n", " ")
            preview = preview[:400] + ("…" if len(preview) > 400 else "")
            raise ValueError(f"Extraction JSON parse failed: {exc}. Preview: {preview}")
    if not isinstance(data, dict):
        raise ValueError("Extraction response must be a JSON object")
    normalized = ensure_extraction_schema(data)
    return raw_json, normalized


def render_summary(extraction: Dict[str, Any], api_key: str) -> str:
    model = genai.GenerativeModel(get_available_model(api_key))
    extraction_json = serialize_extraction(extraction)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        hard_rules=HARD_RULES_PREFACE,
        professional_guidance=PRO_SUMMARY_GUIDANCE,
        extraction_json=extraction_json
    )
    response = model.generate_content(prompt)
    return _response_to_text(response)


def verify_summary(extraction: Dict[str, Any], html_summary: str, api_key: str) -> Tuple[bool, str]:
    model = genai.GenerativeModel(get_available_model(api_key))
    prompt = VERIFIER_PROMPT_TEMPLATE.format(
        hard_rules=HARD_RULES_PREFACE,
        extraction_json=serialize_extraction(extraction),
        summary_html=html_summary
    )
    response = model.generate_content(prompt)
    verdict = _response_to_text(response).strip()
    if verdict == "PASSED":
        return True, verdict
    return False, verdict


def get_field(extraction: Dict[str, Any], dotted_path: str) -> Any:
    current: Any = extraction
    for part in dotted_path.split('.'):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def local_validate(extraction: Dict[str, Any], summary_html: str) -> List[str]:
    mode = (extraction.get("adjudication_mode") or "unknown").lower()
    text = summary_html.lower()
    contradictions: List[str] = []

    if mode != "plea_guilty" and re.search(r"\bplead(?:ed|s)? guilty\b", text):
        contradictions.append("Plea language present but adjudication_mode != plea_guilty")
    if mode == "plea_guilty" and re.search(r"\bfound guilty after a plea of not guilty\b", text):
        contradictions.append("Trial verdict language present but adjudication_mode == plea_guilty")
    if mode not in ("trial_guilty", "plea_guilty") and re.search(r"\bconvicted\b", text):
        contradictions.append("Conviction language present without supporting adjudication_mode")

    counts_supported = set(extraction.get("counts_convicted", [])) | set(extraction.get("counts_dismissed", []))
    mentioned_counts = {int(num) for num in re.findall(r"count(?:s)?(?:\s+number)?\s+(\d+)", text)}
    if mentioned_counts and not mentioned_counts.issubset(counts_supported):
        missing = sorted(mentioned_counts - counts_supported)
        contradictions.append(f"Count references not supported by extraction: {missing}")

    if "sex trafficking" in text and not any("1591" in str(statute).lower() for statute in extraction.get("statutes", [])):
        contradictions.append("Sex trafficking language present without supporting statute in DATA")

    return contradictions


def persist_guard_metadata(cursor, doc_uid: str, extraction_json: Optional[str] = None, verifier_result: Optional[str] = None, verifier_notes: Optional[str] = None) -> None:
    updates: List[str] = []
    params: List[Any] = []
    if extraction_json is not None:
        updates.append("summary_ai_extraction_json = ?")
        params.append(extraction_json)
    if verifier_result is not None:
        updates.append("summary_ai_verifier_result = ?")
        params.append(verifier_result)
    if verifier_notes is not None:
        updates.append("summary_ai_verifier_notes = ?")
        params.append(verifier_notes)
    if not updates:
        return
    params.append(doc_uid)
    sql = f"UPDATE docketwatch.dbo.documents SET {', '.join(updates)} WHERE doc_uid = CAST(? AS uniqueidentifier)"
    try:
        cursor.execute(sql, params)
    except pyodbc.ProgrammingError as exc:
        _simple_log(f"Optional metadata columns missing: {exc}", "WARNING")


def persist_summary(cursor, doc_uid: str, summary_text: str, summary_html: str, extraction_json: Optional[str], verifier_result: Optional[str], verifier_notes: Optional[str]) -> None:
    columns = ["summary_ai = ?", "summary_ai_html = ?", "ai_processed_at = ?"]
    params: List[Any] = [summary_text, summary_html, datetime.now()]
    if extraction_json is not None:
        columns.append("summary_ai_extraction_json = ?")
        params.append(extraction_json)
    if verifier_result is not None:
        columns.append("summary_ai_verifier_result = ?")
        params.append(verifier_result)
    if verifier_notes is not None:
        columns.append("summary_ai_verifier_notes = ?")
        params.append(verifier_notes)
    params.append(doc_uid)
    sql = f"UPDATE docketwatch.dbo.documents SET {', '.join(columns)} WHERE doc_uid = CAST(? AS uniqueidentifier)"
    try:
        cursor.execute(sql, params)
    except pyodbc.ProgrammingError:
        _simple_log("Falling back to legacy summary update (optional columns missing)", "WARNING")
        cursor.execute(
            """
            UPDATE docketwatch.dbo.documents
            SET summary_ai = ?, summary_ai_html = ?, ai_processed_at = ?
            WHERE doc_uid = CAST(? AS uniqueidentifier)
            """,
            (summary_text, summary_html, datetime.now(), doc_uid)
        )

def refine_ocr_with_ai(text: str, api_key: str) -> str:
    genai.configure(api_key=api_key)
    model_name = get_available_model(api_key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""
SYSTEM: You are an expert legal document cleaner.
Your job is to correct OCR errors in legal text while preserving original meaning.
Fix split words, misspellings, and remove junk characters.

--- TEXT TO CLEAN ---
{text[:9000]}
--- END ---

Return only the corrected text. Do not summarize or explain.
"""
    try:
        response = model.generate_content(prompt)
        return response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        if '404' in str(e) and 'not found' in str(e):
            _simple_log(f"Refine OCR model {model_name} 404. Retrying with {model_name}.", "WARNING")
            try:
                fallback = genai.GenerativeModel(model_name)
                response = fallback.generate_content(prompt)
                return response.candidates[0].content.parts[0].text.strip()
            except Exception as inner:
                _simple_log(f"Fallback refine OCR failed: {inner}", "ERROR")
        raise

def ask_gemini(case_summary, event_desc, event_date, pdf_text, api_key):
    genai.configure(api_key=api_key)
    model_name = get_available_model(api_key)
    model = genai.GenerativeModel(model_name)

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

    # Submit with retry handling for model issues
    attempt_models = [model_name, model_name]

    last_err = None
    for idx, mname in enumerate(attempt_models):
        try:
            if idx > 0:
                _simple_log(f"Retrying summary with {mname}", "WARNING")
            alt_model = genai.GenerativeModel(mname)
            response = alt_model.generate_content(full_prompt[:16000])
            # Prefer response.text if present, else drill into candidates
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
            return response.candidates[0].content.parts[0].text.strip()
        except Exception as e:
            last_err = e
            _simple_log(f"Model {mname} error: {e}", "WARNING")
            continue
    _simple_log(f"All model attempts failed: {last_err}", "ERROR")
    raise last_err


def process_single_pdf(doc_uid: str):
    # Setup logging with the script filename
    script_filename = os.path.splitext(os.path.basename(__file__))[0]
    setup_logging(f"u:/docketwatch/python/logs/{script_filename}.log")
    t_start = time.time()
    stage_times = {}

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
        t_ocr_start = time.time()
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
        stage_times['ocr_total_sec'] = round(time.time() - t_ocr_start, 2)

    pdf_text = clean_ocr_text(ocr_text or "")
    if len(pdf_text.strip()) < 100:
        log_message(cur, None, "WARNING", f"Skipping Gemini summary for {doc_uid} - OCR result too poor (length: {len(pdf_text.strip())})")
        print("Skipping Gemini summary — OCR result is too poor.")
        return

    try:
        t_ai_start = time.time()
        log_message(cur, None, "INFO", f"Requesting Gemini summary for {doc_uid}")

        summary_text = ""
        summary_html = ""
        parsed_summary = {}
        extraction_json_str: Optional[str] = None
        verifier_result: Optional[str] = None
        verifier_notes: Optional[str] = None

        if FACT_GUARD:
            log_message(cur, None, "INFO", f"FACT_GUARD enabled for {doc_uid}; using extract-verify pipeline")
            raw_extraction, extraction = extract_facts(pdf_text, summ or "", ev_desc or "", ev_date or "", key)
            extraction_json_str = serialize_extraction(extraction)
            persist_guard_metadata(cur, doc_uid, extraction_json=raw_extraction)

            if not extraction_has_substance(extraction):
                verifier_result = "FAILED_EXTRACTION"
                verifier_notes = "Extractor returned only unknown values."
                persist_guard_metadata(cur, doc_uid, verifier_result=verifier_result, verifier_notes=verifier_notes)
                conn.commit()
                log_message(cur, None, "ERROR", f"Extraction produced no substantive facts for {doc_uid}")
                return

            summary_html = render_summary(extraction, key)
            summary_html = fix_encoding_garbage(summary_html)
            summary_html = normalize_quotes(summary_html)
            summary_text = summary_html

            local_flags = local_validate(extraction, summary_html)
            if local_flags:
                verifier_result = "FAILED_LOCAL"
                verifier_notes = "; ".join(local_flags)
                persist_guard_metadata(cur, doc_uid, verifier_result=verifier_result, verifier_notes=verifier_notes)
                conn.commit()
                log_message(cur, None, "ERROR", f"Local validation failed for {doc_uid}: {verifier_notes}")
                return

            passed, verdict = verify_summary(extraction, summary_html, key)
            verifier_result = "PASSED" if passed else "FAILED"
            verifier_notes = None if verdict == "PASSED" else verdict
            persist_guard_metadata(cur, doc_uid, verifier_result=verifier_result, verifier_notes=verifier_notes)
            if not passed:
                conn.commit()
                log_message(cur, None, "ERROR", f"Verifier rejected summary for {doc_uid}: {verdict}")
                return

            summary_html = BeautifulSoup(summary_html, "html.parser").prettify()
            summary_text = summary_html
            parsed_summary = parse_ai_summary(summary_text)
        else:
            gem = ask_gemini(summ or "", ev_desc or "", ev_date or "", pdf_text, key)
            gem = fix_encoding_garbage(gem)
            gem = normalize_quotes(gem)
            summary_text = gem
            summary_html = BeautifulSoup(markdown2.markdown(gem), "html.parser").prettify()
            parsed_summary = parse_ai_summary(gem)

        stage_times['ai_summary_sec'] = round(time.time() - t_ai_start, 2)

    except Exception as e:
        log_message(cur, None, "ERROR", f"Gemini fail {doc_uid}: {e}")
        return

    if FACT_GUARD:
        persist_summary(cur, doc_uid, summary_text, summary_html, extraction_json_str, verifier_result, verifier_notes)
    else:
        cur.execute(
            """
        UPDATE docketwatch.dbo.documents
        SET summary_ai = ?, summary_ai_html = ?, ai_processed_at = ?
        WHERE doc_uid = CAST(? AS uniqueidentifier)
    """,
            (summary_text, summary_html, datetime.now(), doc_uid)
        )

    try:
        save_structured_summary(cur, doc_uid, parsed_summary, enable_articles=True)
        log_message(cur, None, "INFO", f"PDF {doc_uid} processed with structured data (articles enabled)")
    except Exception as e:
        log_message(cur, None, "WARNING", f"Failed to save structured data for {doc_uid}: {e}")
        log_message(cur, None, "INFO", f"PDF {doc_uid} processed (summary only)")
    
    conn.commit()
    stage_times['total_sec'] = round(time.time() - t_start, 2)
    if stage_times:
        timing_msg = ", ".join(f"{k}={v}" for k, v in stage_times.items())
        log_message(cur, None, "INFO", f"Timing: {timing_msg}")
    cur.close(); conn.close()

def get_default_doc_uid():
    """Get the latest document that needs summarization."""
    conn, cur = get_cursor()
    try:
        # Updated selection logic per request: prioritize today's tracked case documents
        # that have not yet been summarized.
        cur.execute("""
            SELECT TOP 1 p.doc_uid AS default_doc_uid
            FROM docketwatch.dbo.documents p
            LEFT JOIN docketwatch.dbo.case_events e ON e.id = p.fk_case_event
            JOIN docketwatch.dbo.cases c ON c.id = p.fk_case
            WHERE p.summary_ai IS NULL
              AND c.fk_tool = 2
              AND c.status = 'Tracked'
              AND CAST(p.date_downloaded AS DATE) = CAST(GETDATE() AS DATE)
            ORDER BY p.date_downloaded DESC
        """)
        row = cur.fetchone()
        return getattr(row, 'default_doc_uid', None) if row else None
    finally:
        conn.close()

def parse_cli_args(argv):
    """Parse CLI for optional doc_uid and ordering.

    Recognized:
      --order=asc|desc  Choose selection order for default doc (date_downloaded)
      <doc_uid>         If provided (and not starting with --), process that specific doc
    """
    order = 'DESC'  # default newest-first
    doc_uid = None
    for arg in argv:
        if arg.startswith('--order='):
            val = arg.split('=', 1)[1].strip().lower()
            if val in ('asc', 'desc'):
                order = val.upper()
        elif not arg.startswith('--') and doc_uid is None:
            # Treat as doc_uid
            doc_uid = arg.strip()
    return doc_uid, order


def get_default_doc_uid(order: str = 'DESC'):
    """Get a document that needs summarization using specified order by date_downloaded."""
    conn, cur = get_cursor()
    try:
        order_sql = 'ASC' if str(order).upper() == 'ASC' else 'DESC'
        cur.execute(f"""
            SELECT TOP 1 p.doc_uid AS default_doc_uid
            FROM docketwatch.dbo.documents p
            LEFT JOIN docketwatch.dbo.case_events e ON e.id = p.fk_case_event
            JOIN docketwatch.dbo.cases c ON c.id = p.fk_case
            WHERE p.summary_ai IS NULL
              AND c.fk_tool = 2
              AND c.status = 'Tracked'
              AND CAST(p.date_downloaded AS DATE) = CAST(GETDATE() AS DATE)
            ORDER BY p.date_downloaded {order_sql}
        """)
        row = cur.fetchone()
        return getattr(row, 'default_doc_uid', None) if row else None
    finally:
        conn.close()


if __name__ == "__main__":
    doc_arg, order = parse_cli_args(sys.argv[1:])
    if not doc_arg:
        # No doc_uid supplied, find one based on order
        default_doc_uid = get_default_doc_uid(order)
        if default_doc_uid:
            print(f"No doc_uid argument supplied. Selecting by date_downloaded {order}. Doc: {default_doc_uid}")
            process_single_pdf(default_doc_uid)
        else:
            print("No unsummarized documents found for today.")
            print("Usage: python summarize_document_event.py <doc_uid> [--order=asc|desc]")
    else:
        process_single_pdf(doc_arg)
