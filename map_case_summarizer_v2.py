"""
MAP Case Summarizer

Based on proven docketwatch_map_scraper.py pattern
- Uses exact same login and authentication method
- Logs into LA Court Media Access Portal 
- Fetches case details via API
- Sends to Gemini for summarization using EXACT same prompt as PACER
- Saves result to `cases.summarize` and `cases.summarize_html`
"""

import os
import json
import pyodbc
import time
import requests
import logging
import markdown2
import argparse
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scraper_base import log_message

def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

# EXACT same prompt template as PACER summarizer
PROMPT_TEMPLATE = """
You are a legal analyst for a major entertainment news organization. Create a clear, professional summary that helps journalists understand and report on this case.

Analyze the following case and docket data to extract:

* The **case name**, **case number**, **jurisdiction**, and **presiding judge**.
* The **parties involved**, including plaintiff(s), defendant(s), and any other relevant participants.
* A clear **chronological narrative**, summarizing key filings, hearing dates, motions, rulings, settlements, and any procedural milestones. Include **docket numbers** when referencing specific filings.
* Any **unusual or notable filings**, such as sealed documents, emergency motions, high-profile attorneys, or withdrawn filings.
* The **current status** of the case (e.g., active, dismissed, settled, judgment entered). If the most recent filing is old or the case is inactive, indicate that clearly.

If related case numbers, consolidation, or cross-filings are noted, include them.

Close with a short section titled **"Why It Matters"**, explaining the case's potential relevance to the entertainment industry, public interest, or legal precedent.

Use neutral, objective language. Do not guess or invent facts. If information is missing or unclear, state that directly.

Keep the summary under 800 words unless critical details require more.

Below is the case docket data:

"""

MAX_INPUT_LENGTH = 16000

def convert_to_clean_html(summary_text):
    """Convert markdown summary to clean HTML - EXACT same function as PACER"""
    html = markdown2.markdown(summary_text)
    soup = BeautifulSoup(html, "html.parser")

    for p in soup.find_all("p"):
        if p.text.strip().startswith("Case Summary:"):
            p.decompose()
            break

    for p in soup.find_all("p"):
        if "Case Name:" in p.decode_contents() and "Case Number:" in p.decode_contents():
            new_html = p.decode_contents()
            new_html = new_html.replace("<strong>Case Number:", "<br/><strong>Case Number:")
            new_html = new_html.replace("<strong>Jurisdiction:", "<br/><strong>Jurisdiction:")
            new_html = new_html.replace("<strong>Presiding Judge:", "<br/><strong>Presiding Judge:")
            p.clear()
            p.append(BeautifulSoup(new_html, "html.parser"))
            break

    for p in soup.find_all("p"):
        if len(p.contents) == 1 and p.contents[0].name == "strong":
            content = p.contents[0].text.strip()
            if content.endswith(":"):
                content = content[:-1]
            h3 = soup.new_tag("h3")
            h3.string = content
            p.replace_with(h3)

    return str(soup)

def summarize_case_data(case_data_text, api_key):
    """Send case data to Gemini for summarization - EXACT same function as PACER"""
    prompt = PROMPT_TEMPLATE + case_data_text[:MAX_INPUT_LENGTH]
    print(f"Prompt length: {len(prompt)}")
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.6, "max_output_tokens": 1000}
            }),
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("candidates"):
            print("Gemini response (no candidates):", json.dumps(result, indent=2))
            return None
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.Timeout:
        print("Gemini API timeout")
        return None
    except Exception as e:
        print("Gemini API error:", e)
        return None

def format_case_data_for_summary(api_data):
    """Convert API JSON data to text format for Gemini summarization"""
    try:
        if not api_data or not api_data.get("ResultList"):
            return "No case data available"
        
        case_info = api_data["ResultList"][0]
        header_info = case_info.get("HeaderInformation", [])
        non_criminal_info = case_info.get("NonCriminalCaseInformation", {})
        
        # Build formatted text
        formatted_text = "=== CASE INFORMATION ===\n\n"
        
        # Header Information
        for item in header_info:
            key = item.get("Key", "")
            value = item.get("Value", "")
            if key and value:
                formatted_text += f"{key}: {value}\n"
        
        formatted_text += "\n=== CASE DETAILS ===\n\n"
        
        # Case Information
        case_details = non_criminal_info.get("CaseInformation", {})
        if case_details:
            litigation_type = case_details.get("LitigationTypeObject", {}).get("Description", "")
            if litigation_type:
                formatted_text += f"Case Type: {litigation_type}\n"
        
        # Register of Actions (Docket Entries)
        actions = non_criminal_info.get("RegisterOfActions", [])
        if actions:
            formatted_text += "\n=== REGISTER OF ACTIONS (CHRONOLOGICAL) ===\n\n"
            for action in actions:
                date = action.get("RegisterOfActionDateString", "")
                description = action.get("Description", "")
                additional = action.get("AdditionalInformation", "")
                
                if date and description:
                    formatted_text += f"Date: {date}\n"
                    formatted_text += f"Description: {description}\n"
                    if additional:
                        formatted_text += f"Additional Info: {additional}\n"
                    formatted_text += "\n"
        
        # Future Proceedings (Hearings)
        hearings = non_criminal_info.get("FutureProceedings", [])
        if hearings:
            formatted_text += "=== FUTURE PROCEEDINGS ===\n\n"
            for hearing in hearings:
                date = hearing.get("ProceedingDateString", "")
                time = hearing.get("ProceedingTime", "")
                ampm = hearing.get("AMPM", "")
                event = hearing.get("Event", "")
                room = hearing.get("ProceedingRoom", "")
                judge = hearing.get("Judge", "")
                result = hearing.get("Result", "")
                
                if date and event:
                    formatted_text += f"Date: {date} {time} {ampm}\n"
                    formatted_text += f"Event: {event}\n"
                    if room:
                        formatted_text += f"Room: {room}\n"
                    if judge:
                        formatted_text += f"Judge: {judge}\n"
                    if result:
                        formatted_text += f"Result: {result}\n"
                    formatted_text += "\n"
        
        # Party Information
        parties = non_criminal_info.get("PartyInformation", [])
        if parties:
            formatted_text += "=== PARTY INFORMATION ===\n\n"
            for party in parties:
                party_type = party.get("PartyType", "")
                party_name = party.get("PartyName", "")
                if party_type and party_name:
                    formatted_text += f"{party_type}: {party_name}\n"
        
        return formatted_text
        
    except Exception as e:
        print(f"Error formatting case data: {e}")
        return f"Error formatting case data: {str(e)}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", type=int, help="Summarize a single case by ID")
    args = parser.parse_args()

    # === GET SCRIPT NAME ===
    script_filename = os.path.splitext(os.path.basename(__file__))[0]

    # === DATABASE CONNECTION & TASK RUN ===
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1 r.id as fk_task_run 
        FROM docketwatch.dbo.task_runs r
        INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
        WHERE s.filename = ? 
        ORDER BY r.id DESC
    """, (script_filename,))
    task_run = cursor.fetchone()
    fk_task_run = task_run[0] if task_run else None

    # === LOGGING SETUP ===
    LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    log_message(cursor, fk_task_run, "INFO", "=== MAP Case Summarizer Started ===")

    # === Setup ChromeDriver ===
    CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    log_message(cursor, fk_task_run, "INFO", "ChromeDriver initialized.")

    # === Fetch credentials and URLs from DB (tool id = 12) ===
    cursor.execute("""
        SELECT [login_url], [username], [pass], [search_url]
        FROM [docketwatch].[dbo].[tools]
        WHERE id = 12
    """)
    login_row = cursor.fetchone()
    if not login_row:
        log_message(cursor, fk_task_run, "ERROR", "No credentials found for tool id 12.")
        driver.quit()
        conn.close()
        return
    login_url, username, password, _ = login_row
    log_message(cursor, fk_task_run, "INFO", "Fetched login credentials from database.")

    # === Get Gemini API key ===
    gemini_key = get_gemini_key(cursor)
    if not gemini_key:
        log_message(cursor, fk_task_run, "ERROR", "No Gemini API key found")
        driver.quit()
        conn.close()
        return

    # === Step 1: Log into the page (exact same as working scraper) ===
    try:
        log_message(cursor, fk_task_run, "INFO", "Navigating to login page...")
        driver.get(login_url)

        wait = WebDriverWait(driver, 20)
        log_message(cursor, fk_task_run, "INFO", "Waiting for login form to appear...")

        wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()

        log_message(cursor, fk_task_run, "INFO", "Login submitted, waiting for OpenID redirect...")
        time.sleep(5)

        if "signin-oidc" in driver.current_url or "media.lacourt.org" in driver.current_url:
            log_message(cursor, fk_task_run, "INFO", "Login successful.")
        else:
            log_message(cursor, fk_task_run, "ERROR", f"Login may have failed. Current URL: {driver.current_url}")
            driver.quit()
            conn.close()
            return

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Login failed: {str(e)}")
        driver.quit()
        conn.close()
        return

    # === Step 2: Extract .AspNetCore.Cookies (exact same as working scraper) ===
    cookies = driver.get_cookies()
    cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
    driver.quit()
    log_message(cursor, fk_task_run, "INFO", "Extracted auth cookie from session.")

    if not auth_cookie:
        log_message(cursor, fk_task_run, "ERROR", "Failed to extract authentication cookie")
        conn.close()
        return

    # === Fetch cases that need summarization ===
    if args.case_id:
        cursor.execute("""
            SELECT [case_number], [map_id], id as [fk_case], [case_name]
            FROM [docketwatch].[dbo].[cases]
            WHERE id = ? AND fk_tool = 12
        """, (args.case_id,))
    else:
        cursor.execute("""
            SELECT [case_number], [map_id], id as [fk_case], [case_name]
            FROM [docketwatch].[dbo].[cases]
            WHERE fk_tool = 12 
              AND status = 'Tracked' 
              AND map_id IS NOT NULL 
              AND (summarize IS NULL OR LEN(LTRIM(RTRIM(ISNULL(summarize, '')))) = 0)
            ORDER BY last_updated
        """)
    
    tool_cases = cursor.fetchall()
    if not tool_cases:
        log_message(cursor, fk_task_run, "INFO", "No tracked cases found that need summarization.")
        conn.close()
        return

    # Safety limit
    max_cases = 50 if not args.case_id else 1
    if len(tool_cases) > max_cases:
        log_message(cursor, fk_task_run, "WARNING", f"Limiting processing to {max_cases} cases (found {len(tool_cases)})")
        tool_cases = tool_cases[:max_cases]

    log_message(cursor, fk_task_run, "INFO", f"Found {len(tool_cases)} cases to summarize.")

    # === Create session with auth cookie (exact same as working scraper) ===
    session = requests.Session()
    session.headers.update({"cookie": f".AspNetCore.Cookies={auth_cookie}"})

    processed_count = 0
    for case_number, map_id, fk_case, case_name in tool_cases:
        processed_count += 1
        print(f"\nProcessing MAP Case {processed_count}/{len(tool_cases)}: {case_number} — {case_name} — MAP ID: {map_id}")
        log_message(cursor, fk_task_run, "INFO", f"Processing case {case_number} for summarization", fk_case=fk_case)
        
        api_url = f"https://media.lacourt.org/api/AzureApi/GetCaseDetail/{map_id}"
        
        try:
            response = session.get(api_url)
            response.raise_for_status()
            data = response.json()
            log_message(cursor, fk_task_run, "INFO", f"Retrieved API data for case {case_number}.", fk_case=fk_case)

            # Format the data for Gemini
            formatted_case_data = format_case_data_for_summary(data)
            log_message(cursor, fk_task_run, "INFO", f"Formatted case data for summarization", fk_case=fk_case)
            
            # Send to Gemini for summarization
            summary = summarize_case_data(formatted_case_data, gemini_key)

            if summary:
                html_version = convert_to_clean_html(summary)
                print(f"Summary received. Saving to case ID: {fk_case}")
                log_message(cursor, fk_task_run, "INFO", f"Gemini summary generated successfully", fk_case=fk_case)
                
                cursor.execute(
                    "UPDATE docketwatch.dbo.cases SET summarize = ?, summarize_html = ? WHERE id = ?",
                    (summary[:4000], html_version[:8000], fk_case)
                )
                conn.commit()
                log_message(cursor, fk_task_run, "SUCCESS", f"Summary saved for case {case_number}", fk_case=fk_case)
                print(f"Success: Summary saved for case {case_number}")
            else:
                log_message(cursor, fk_task_run, "WARNING", f"Gemini returned no summary for case {case_number}", fk_case=fk_case)
                print(f"Warning: Gemini returned no summary for case {case_number}")
                
            # Small delay to prevent overwhelming APIs
            time.sleep(2)

        except Exception as e:
            log_message(cursor, fk_task_run, "ERROR", f"Failed to summarize case {case_number}: {str(e)}", fk_case=fk_case)
            print(f"Error processing case {case_number}: {str(e)}")
            continue

    # === Cleanup ===
    cursor.close()
    conn.close()
    log_message(cursor, fk_task_run, "INFO", "=== MAP Case Summarizer Completed ===")
    print("MAP Case Summarizer Completed")

if __name__ == "__main__":
    main()
