import requests
import json
import markdown2
from bs4 import BeautifulSoup
from datetime import datetime

def clean_map_case_data(raw_data):
    """
    Cleans and reduces MAP JSON structure to essential case data for summarization.

    Args:
        raw_data: full MAP JSON object (dict)

    Returns:
        cleaned dict suitable for summarization
    """
    try:
        result = raw_data["ResultList"][0]
        cleaned = {
            "HeaderInformation": result.get("HeaderInformation", []),
            "CaseInformation": result.get("NonCriminalCaseInformation", {}).get("CaseInformation", {}),
            "Parties": result.get("NonCriminalCaseInformation", {}).get("Parties", []),
            "DocumentsFiled": result.get("NonCriminalCaseInformation", {}).get("DocumentsFiled", []),
            "RegisterOfActions": result.get("NonCriminalCaseInformation", {}).get("RegisterOfActions", []),
            "PastProceedings": result.get("NonCriminalCaseInformation", {}).get("PastProceedings", []),
            "FutureProceedings": result.get("NonCriminalCaseInformation", {}).get("FutureProceedings", [])
        }
        return cleaned
    except Exception as e:
        print(f"[!] Error cleaning MAP case data: {e}")
        return raw_data  # fallback to uncleaned

def generate_and_save_map_summary(cursor, conn, fk_case, case_number, case_name, map_case_data, gemini_key):
    """
    Summarizes a MAP case using Gemini and stores the result in `cases.summarize` and `summarize_html`.

    Args:
        cursor: active DB cursor
        conn: active DB connection
        fk_case: ID of the case in `cases` table
        case_number: court case number string
        case_name: full case name
        map_case_data: parsed JSON object returned from GetCaseDetail
        gemini_key: API key for Gemini 1.5

    Returns:
        True if summary was generated and saved, False otherwise
    """
    cleaned_data = clean_map_case_data(map_case_data)

    prompt = f"""
You are a legal analyst summarizing a civil case for an internal newsroom research tool.

Summarize the key details of this court case based solely on the following JSON data from the court's API.

Include:
- Case number, case title, case type, filing date, courthouse, judicial officer.
- Petitioner(s) and respondent(s).
- Key documents filed (title + date).
- Any past proceedings and their results.
- Register of actions (chronological summary).
- Case disposition and current status.
- If relevant, include why this case might interest a news outlet.

Use plain English. Be concise but informative. Max 500 words.

--- START JSON ---
{json.dumps(cleaned_data, indent=2)}
--- END JSON ---
"""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={gemini_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1200}
            }),
            timeout=90
        )
        response.raise_for_status()
        gemini_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        html_version = BeautifulSoup(markdown2.markdown(gemini_text), "html.parser").prettify()

        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET summarize = ?, summarize_html = ?, ai_processed_at = ?
            WHERE id = ?
        """, (gemini_text[:4000], html_version[:8000], datetime.now(), fk_case))
        conn.commit()

        print(f"[+] Gemini summary saved for case {case_number} ({case_name})")
        return True

    except Exception as e:
        print(f"[!] Gemini summary failed for case {case_number} ({case_name}): {e}")
        return False
