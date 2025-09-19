"""
PACER Case Summarizer

- Logs into PACER usinClose with a short section titled **"Why It Matters"**, explaining the case's potential relevance to the entertainment industry, public interest, or legal precedent. custom login method
- Navigates to each case URL and clicks into full docket report
- Ensures 'list_of_parties_and_counsel' is checked, 'terminated_parties' is unchecked
- Extracts HTML of full docket page (no date filtering)
- Sends to Gemini for summarization
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
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from scraper_base import get_db_cursor, get_task_context_by_tool_id, log_message, DEFAULT_CHROMEDRIVER_PATH

def human_pause(a, b):
    time.sleep((a + b) / 2)

def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

PROMPT_TEMPLATE = """
You are a legal analyst for a major entertainment news organization. Create a clear, professional summary that helps journalists understand and report on this case.

Analyze the following case and docket data to extract:

* The **case name**, **case number**, **jurisdiction**, and **presiding judge**.
* The **parties involved**, including plaintiff(s), defendant(s), and any other relevant participants.
* A clear **chronological narrative**, summarizing key filings, hearing dates, motions, rulings, settlements, and any procedural milestones. Include **docket numbers** when referencing specific filings.
* Any **unusual or notable filings**, such as sealed documents, emergency motions, high-profile attorneys, or withdrawn filings.
* The **current status** of the case (e.g., active, dismissed, settled, judgment entered). If the most recent filing is old or the case is inactive, indicate that clearly.

If related case numbers, consolidation, or cross-filings are noted, include them.

Close with a short section titled **"Why It Matters"**, explaining the case’s potential relevance to the entertainment industry, public interest, or legal precedent.

Use neutral, objective language. Do not guess or invent facts. If information is missing or unclear, state that directly.

Keep the summary under 800 words unless critical details require more.

Below is the case docket data:

"""

MAX_INPUT_LENGTH = 16000

def clean_html(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return ' '.join(soup.get_text().split())

def convert_to_clean_html(summary_text):
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
    if single_case_id:
        cursor.execute("SELECT id, id AS fk_case, case_number, case_name, case_url FROM docketwatch.dbo.cases WHERE id = ?", (single_case_id,))
    else:
        cursor.execute("""SELECT DISTINCT c.id, c.id AS fk_case, c.case_number, CAST(c.case_name AS NVARCHAR(MAX)) as case_name, c.case_url,
                CAST(d.summary_ai AS NVARCHAR(MAX)) as doc_summary, 
                CAST(e.summarize AS NVARCHAR(MAX)) as event_summary, 
                CAST(c.summarize AS NVARCHAR(MAX)) as case_summary,
                d.date_downloaded
                FROM docketwatch.dbo.cases c
                INNER JOIN docketwatch.dbo.case_events e ON e.fk_cases = c.id
                INNER JOIN docketwatch.dbo.documents d ON d.fk_case_event = e.id
                Where  c.case_number <> 'Unfiled' and d.summary_ai is  null and  c.summarize is not null
           and c.fk_tool = 2 AND d.rel_path IS NOT NULL  AND c.summarize IS not NULL

    	   order by d.date_downloaded desc""")
    
    # Handle potential encoding issues when fetching results
    try:
        return cursor.fetchall()
    except UnicodeDecodeError as e:
        print(f"Unicode decode error: {e}")
        print("Attempting to handle encoding issue...")
        
        # Re-execute with explicit encoding handling
        if single_case_id:
            cursor.execute("SELECT id, id AS fk_case, case_number, CAST(case_name AS NVARCHAR(MAX)) as case_name, case_url FROM docketwatch.dbo.cases WHERE id = ?", (single_case_id,))
        else:
            cursor.execute("""SELECT DISTINCT c.id, c.id AS fk_case, c.case_number, CAST(c.case_name AS NVARCHAR(MAX)) as case_name, c.case_url,
                CAST(d.summary_ai AS NVARCHAR(MAX)) as doc_summary, 
                CAST(e.summarize AS NVARCHAR(MAX)) as event_summary, 
                CAST(c.summarize AS NVARCHAR(MAX)) as case_summary,
                d.date_downloaded
                FROM docketwatch.dbo.cases c
                INNER JOIN docketwatch.dbo.case_events e ON e.fk_cases = c.id
                INNER JOIN docketwatch.dbo.documents d ON d.fk_case_event = e.id
                Where  c.case_number <> 'Unfiled' and d.summary_ai is  null and  c.summarize is not null
           and c.fk_tool = 2 AND d.rel_path IS NOT NULL  AND c.summarize IS not NULL

    	   order by d.date_downloaded desc""")
        return cursor.fetchall()

def summarize_case_html(html_text, api_key):
    prompt = PROMPT_TEMPLATE + html_text[:MAX_INPUT_LENGTH]
    print(f"Prompt length: {len(prompt)}")
    
    # Try different models, starting with the fastest/least loaded
    models_to_try = [
        "gemini-1.5-flash",  # Fastest model, less likely to be overloaded
        "gemini-1.5-pro",   # Original model (fallback)
        "gemini-pro"        # Older model (last resort)
    ]
    
    for model_name in models_to_try:
        print(f"Trying model: {model_name}")
        
        for attempt in range(3):  # Up to 3 retries per model
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.6, "max_output_tokens": 1000}
                    })
                )
                result = response.json()
                
                # Check for success
                if response.status_code == 200 and result.get("candidates"):
                    print(f"[SUCCESS] Success with {model_name} on attempt {attempt + 1}")
                    return result["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Handle specific error cases
                if response.status_code == 503:
                    wait_time = (attempt + 1) * 10  # 10, 20, 30 seconds
                    print(f"503 overloaded error with {model_name}, waiting {wait_time}s before retry {attempt + 1}/3")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 403:
                    print(f"403 permission error with {model_name}, trying next model")
                    break  # Try next model
                else:
                    print(f"Unexpected response ({response.status_code}) with {model_name}:", json.dumps(result, indent=2))
                    break  # Try next model
                    
            except Exception as e:
                print(f"Request error with {model_name} attempt {attempt + 1}: {e}")
                if attempt < 2:  # Don't wait on last attempt
                    time.sleep(5)
    
    print("[ERROR] All models failed or overloaded")
    return None

def login_to_pacer(driver, username, password, cursor, fk_task_run):
    try:
        driver.get("https://pacer.login.uscourts.gov/csologin/login.jsf")
        human_pause(2, 4)
        driver.find_element(By.NAME, "loginForm:loginName").send_keys(username)
        driver.find_element(By.NAME, "loginForm:password").send_keys(password)
        try:
            code_field = driver.find_element(By.NAME, "loginForm:clientCode")
            code_field.clear()
            code_field.send_keys("DocketWatch")
        except:
            pass
        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        human_pause(3, 5)
        log_message(cursor, fk_task_run, "INFO", "PACER login successful.")
        print("PACER login successful.")
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"PACER login failed: {e}")
        print("PACER login failed:", e)
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", type=int, help="Summarize a single case by ID")
    args = parser.parse_args()

    conn, cursor = get_db_cursor()
    context = get_task_context_by_tool_id(cursor, 2)
    gemini_key = get_gemini_key(cursor)
    username = context.get("username")
    password = context.get("pass")

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")  
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--max_old_space_size=4096")
    driver = webdriver.Chrome(service=Service(DEFAULT_CHROMEDRIVER_PATH), options=options)

    try:
        login_to_pacer(driver, username, password, cursor, context["fk_task_run"])
        cases = get_target_cases(cursor, args.case_id)

        for case_row in cases:
            # Handle different query results - single case vs multi-case
            if len(case_row) == 5:  # Single case query
                case_id, fk_case, case_number, case_name, case_url = case_row
            else:  # Multi-case query with additional fields
                case_id, fk_case, case_number, case_name, case_url = case_row[:5]
                
            # Handle potential encoding issues in individual fields
            try:
                case_name_safe = str(case_name) if case_name else "Unknown Case"
                case_number_safe = str(case_number) if case_number else "Unknown"
                case_url_safe = str(case_url) if case_url else ""
            except UnicodeDecodeError:
                case_name_safe = "Case with encoding issue"
                case_number_safe = str(case_id)
                case_url_safe = case_url if case_url else ""
                
            print(f"\nProcessing Case: {case_number_safe} - {case_name_safe} - {case_url_safe}")
            log_id = log_message(cursor, context["fk_task_run"], "INFO", f"Reviewing case: {case_name_safe}", fk_case=fk_case)
            cursor.execute("UPDATE dbo.cases SET fk_task_run_log = ? WHERE id = ?", (log_id, case_id))
            conn.commit()

            try:
                driver.get(case_url_safe)
                human_pause(3, 5)
                log_message(cursor, context["fk_task_run"], "INFO", f"Loaded case URL: {case_url_safe}", fk_case=fk_case)
                print("Loaded case URL")
                driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report").click()
                human_pause(2, 3)
                log_message(cursor, context["fk_task_run"], "INFO", f"Clicked into Docket Report screen", fk_case=fk_case)
                print("Clicked Docket Report")

                try:
                    checkbox = driver.find_element(By.ID, "list_of_parties_and_counsel")
                    if not checkbox.is_selected():
                        checkbox.click()
                except Exception as e:
                    log_message(cursor, context["fk_task_run"], "WARNING", f"Checkbox issue: {e}", fk_case=fk_case)
                    print("Checkbox issue:", e)

                try:
                    checkbox = driver.find_element(By.ID, "terminated_parties")
                    if checkbox.is_selected():
                        checkbox.click()
                except:
                    pass

                try:
                    Select(driver.find_element(By.NAME, "sort1")).select_by_visible_text("Most recent date first")
                except Exception as e:
                    log_message(cursor, context["fk_task_run"], "WARNING", f"Sort dropdown issue: {e}", fk_case=fk_case)
                    print("Sort dropdown issue:", e)

                driver.find_element(By.NAME, "button1").click()
                human_pause(3, 5)
                log_message(cursor, context["fk_task_run"], "INFO", f"Submitted docket report form", fk_case=fk_case)
                print("Submitted form")

                html = driver.page_source
                clean_text = clean_html(html)
                summary = summarize_case_html(clean_text, gemini_key)

                if summary:
                    html_version = convert_to_clean_html(summary)
                    print(f"Summary received. Saving to case ID: {case_id}")
                    cursor.execute(
                        "UPDATE docketwatch.dbo.cases SET summarize = ?, summarize_html = ? WHERE id = ?",
                        (summary[:4000], html_version[:8000], case_id)
                    )
                    conn.commit()
                else:
                    print("Gemini returned no summary.")
            except Exception as e:
                log_message(cursor, context["fk_task_run"], "ERROR", f"Failed to summarize case {case_number_safe}: {e}", fk_case=fk_case)
                print(f"Error processing case {case_number_safe}: {e}")
                continue
    finally:
        driver.quit()
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
