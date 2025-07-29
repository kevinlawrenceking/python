"""
MAP Case Summarizer

- Logs into LA Court Media Access Portal using existing authentication method
- Navigates to each case via API and extracts case details and docket information
- Sends to Gemini for summarization using the EXACT same prompt as PACER
- Saves result to `cases.summarize` and `cases.summarize_html`
"""

import os
import sys
import time
import argparse
import logging
import pyodbc
import json
import requests
import markdown2
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scraper_base import get_db_cursor, get_task_context_by_tool_id, log_message, DEFAULT_CHROMEDRIVER_PATH

def human_pause(a, b):
    time.sleep((a + b) / 2)

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

def get_target_cases(cursor, single_case_id=None):
    """Get MAP cases that need summarization"""
    if single_case_id:
        cursor.execute("""
            SELECT id, id AS fk_case, case_number, case_name, map_id 
            FROM docketwatch.dbo.cases 
            WHERE id = ? AND fk_tool = 12
        """, (single_case_id,))
    else:
        cursor.execute("""
            SELECT id, id AS fk_case, case_number, case_name, map_id
            FROM docketwatch.dbo.cases 
            WHERE fk_tool = 12 
              AND status = 'Tracked' 
              AND map_id IS NOT NULL 
              AND summarize IS NULL
            ORDER BY last_updated
        """)
    return cursor.fetchall()

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
            })
        )
        result = response.json()
        if not result.get("candidates"):
            print("Gemini response (no candidates):", json.dumps(result, indent=2))
            return None
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("Gemini API error:", e)
        return None

def login_to_map(driver, username, password, login_url, cursor, fk_task_run):
    """Login to LA Court Media Access Portal"""
    try:
        log_message(cursor, fk_task_run, "INFO", "Navigating to MAP login page...")
        driver.get(login_url)
        wait = WebDriverWait(driver, 20)
        
        log_message(cursor, fk_task_run, "INFO", "Waiting for login form to appear...")
        wait.until(EC.presence_of_element_located((By.ID, "logonIdentifier"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.ID, "next"))).click()
        
        log_message(cursor, fk_task_run, "INFO", "Login submitted, waiting for OpenID redirect...")
        time.sleep(5)
        
        if "signin-oidc" in driver.current_url or "media.lacourt.org" in driver.current_url:
            log_message(cursor, fk_task_run, "INFO", "MAP login successful.")
            print("MAP login successful.")
        else:
            log_message(cursor, fk_task_run, "ERROR", f"Login may have failed. Current URL: {driver.current_url}")
            raise Exception("MAP login failed")
            
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"MAP login failed: {e}")
        print("MAP login failed:", e)
        raise

def extract_auth_cookie(driver):
    """Extract authentication cookie from browser session"""
    cookies = driver.get_cookies()
    cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    auth_cookie = cookie_dict.get(".AspNetCore.Cookies")
    return auth_cookie

def get_case_data_from_api(map_id, auth_cookie, cursor, fk_task_run, fk_case):
    """Fetch case details from MAP API"""
    try:
        headers = {"cookie": f".AspNetCore.Cookies={auth_cookie}"}
        api_url = f"https://media.lacourt.org/api/AzureApi/GetCaseDetail/{map_id}"
        
        log_message(cursor, fk_task_run, "INFO", f"Making API request to {api_url}", fk_case=fk_case)
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        log_message(cursor, fk_task_run, "INFO", f"Successfully retrieved API data for MAP ID {map_id}", fk_case=fk_case)
        
        return data
        
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Failed to fetch API data for MAP ID {map_id}: {e}", fk_case=fk_case)
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

    conn, cursor = get_db_cursor()
    context = get_task_context_by_tool_id(cursor, 12)  # MAP tool ID is 12
    gemini_key = get_gemini_key(cursor)
    
    if not context:
        print("Error: No context found for MAP tool (ID 12)")
        return
        
    username = context.get("username")
    password = context.get("pass")
    login_url = context.get("login_url")

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")  
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-extensions")
    driver = webdriver.Chrome(service=Service(DEFAULT_CHROMEDRIVER_PATH), options=options)

    try:
        # Login to MAP and get authentication cookie
        login_to_map(driver, username, password, login_url, cursor, context["fk_task_run"])
        auth_cookie = extract_auth_cookie(driver)
        driver.quit()  # We don't need the browser anymore after getting the cookie
        
        if not auth_cookie:
            log_message(cursor, context["fk_task_run"], "ERROR", "Failed to extract authentication cookie")
            return
        
        log_message(cursor, context["fk_task_run"], "INFO", "Successfully extracted authentication cookie")
        
        # Get cases that need summarization
        cases = get_target_cases(cursor, args.case_id)
        
        if not cases:
            log_message(cursor, context["fk_task_run"], "INFO", "No MAP cases found that need summarization")
            print("No MAP cases found that need summarization")
            return

        log_message(cursor, context["fk_task_run"], "INFO", f"Found {len(cases)} MAP cases to summarize")

        for case_id, fk_case, case_number, case_name, map_id in cases:
            print(f"\nProcessing MAP Case: {case_number} — {case_name} — MAP ID: {map_id}")
            log_id = log_message(cursor, context["fk_task_run"], "INFO", f"Reviewing MAP case: {case_name}", fk_case=fk_case)
            cursor.execute("UPDATE dbo.cases SET fk_task_run_log = ? WHERE id = ?", (log_id, case_id))
            conn.commit()

            try:
                # Get case data from MAP API
                api_data = get_case_data_from_api(map_id, auth_cookie, cursor, context["fk_task_run"], fk_case)
                
                if not api_data:
                    log_message(cursor, context["fk_task_run"], "ERROR", f"No API data received for case {case_number}", fk_case=fk_case)
                    continue
                
                # Format the data for Gemini
                formatted_case_data = format_case_data_for_summary(api_data)
                log_message(cursor, context["fk_task_run"], "INFO", f"Formatted case data for summarization", fk_case=fk_case)
                
                # Send to Gemini for summarization
                summary = summarize_case_data(formatted_case_data, gemini_key)

                if summary:
                    html_version = convert_to_clean_html(summary)
                    print(f"Summary received. Saving to case ID: {case_id}")
                    log_message(cursor, context["fk_task_run"], "INFO", f"Gemini summary generated successfully", fk_case=fk_case)
                    
                    cursor.execute(
                        "UPDATE docketwatch.dbo.cases SET summarize = ?, summarize_html = ? WHERE id = ?",
                        (summary[:4000], html_version[:8000], case_id)
                    )
                    conn.commit()
                    log_message(cursor, context["fk_task_run"], "SUCCESS", f"Summary saved for case {case_number}", fk_case=fk_case)
                else:
                    log_message(cursor, context["fk_task_run"], "WARNING", f"Gemini returned no summary for case {case_number}", fk_case=fk_case)
                    print("Gemini returned no summary.")
                    
            except Exception as e:
                log_message(cursor, context["fk_task_run"], "ERROR", f"Failed to summarize case {case_number}: {e}", fk_case=fk_case)
                print(f"Error processing case {case_number}: {e}")
                continue

        log_message(cursor, context["fk_task_run"], "INFO", "MAP case summarization completed")
        
    except Exception as e:
        log_message(cursor, context["fk_task_run"], "ERROR", f"MAP summarizer failed: {e}")
        print(f"MAP summarizer failed: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
