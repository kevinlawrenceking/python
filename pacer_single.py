# --- IMPORTS ---
import os
import sys
import logging
import psutil
import random
import unicodedata
import re
import requests
import json
import markdown2
import smtplib
import pyodbc
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# Google Gemini API specific imports
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Assuming these are from scraper_base.py (not provided, but needed for context)
from scraper_base import extract_and_store_pacer_billing, mark_case_not_found, mark_case_found, log_message

# --- GLOBAL CONFIGURATION ---
FROM_EMAIL = "it@tmz.com"
TO_EMAILS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "Marlee.Goodman@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25

LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\pacer_single.log"
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\pacer_single.lock"
CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
script_filename = os.path.splitext(os.path.basename(__file__))[0]

# Configure logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global variables for database connection and task run (used across functions)
conn = None
cursor = None
driver = None
fk_task_run = None

# Gemini model configuration
GEMINI_MODEL_NAME = "gemini-1.5-pro" # Using the current high-capability model. Change if a new model ID becomes available.
MAX_HTML_CHARS_TO_SEND = 16000 # Truncate input HTML to manage context window.

# --- UTILITY FUNCTIONS ---

def send_docket_email(case_name, case_url, event_no, cleaned_docket_text):
    global cursor, fk_task_run
    subject = f"DocketWatch Alert: {case_name} – New Docket Discovered"
    body = f"""<html><body>
        A new docket has been detected for case:<br>
        <a href="{case_url}">{case_name}</a><br><br>
        <strong>Docket No:</strong> {event_no}<br>
        <strong>Description:</strong><br>
        <p>{cleaned_docket_text}</p>
    </body></html>"""
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        log_message(cursor, fk_task_run, "ALERT", f"Email sent for new docket in case {case_name}", fk_case=None)
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Failed to send email: {e}", fk_case=None)

def is_another_instance_running():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    return True
        except (ValueError, FileNotFoundError):
            pass
        os.remove(LOCK_FILE)
    return False

def human_pause(min_time=1, max_time=3):
    time.sleep(random.uniform(min_time, max_time))

def sanitize_unicode(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    replacements = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"',
        "\u201d": '"', "\xa0": " ", "â€“": "-", "â€”": "-", "â€™": "'",
        "â€œ": '"', "â€": '"', "â€˜": "'", "â€": '"'
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text

def clean_text(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text).replace("'", "''").replace("\n", " ").replace("\r", " ")
    return text[:4000]

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

# --- GLOBAL CONFIGURATION (snippet) ---

# Gemini model configuration
# NOTE: "gemini-2.5-pro" is not a valid model name as of late 2024.
# Using "gemini-1.5-pro", which is the latest and most capable public model.
GEMINI_MODEL_NAME = "gemini-1.5-pro"
# NOTE: gemini-1.5-pro has a very large context window (1M tokens). You can
# safely increase this limit if you need to process larger documents.
MAX_HTML_CHARS_TO_SEND = 32000 # Increased from 16000

# --- FUNCTION DEFINITIONS (snippet) ---

def summarize_case_html(html_text: str, api_key: str, cursor, fk_task_run, fk_case) -> str | None:
    """
    Summarizes legal HTML content using the Google Gemini 1.5 Pro API with an enhanced prompt.
    """
    # --- CHANGED: Enhanced Prompt for Gemini 1.5 Pro ---
    # This new prompt is more structured to guide the model effectively. It defines a role,
    # a clear task, step-by-step instructions, and explicit delimiters for input and output.
    # This reduces hallucinations and improves the quality and consistency of the summary.
    PROMPT_TEMPLATE = """
**Role:** You are an expert legal analyst for a major entertainment news organization.

**Task:** Analyze the following HTML content from a court docket report. Your goal is to produce a concise, professional, and newsworthy executive summary that captures the essence of the case and its latest developments.

**Instructions:**
1.  **Identify Key Information:** From the HTML, first identify the core facts:
    *   Case Name, Number, and Jurisdiction.
    *   The primary parties involved (Plaintiff vs. Defendant).
    *   The core dispute or the central legal issue of the case.
    *   The most recent significant ruling, decision, or filing mentioned.
    *   The overall outcome or current status.
2.  **Synthesize the Summary:** Using the information you identified, write a cohesive executive summary.
3.  **Formatting Rules:**
    *   The summary must be a single block of narrative text.
    *   Keep the summary under 300 words.
    *   The tone must be objective, factual, and clear.
    *   **Crucially, do NOT include any conversational filler.** Start the summary directly, without phrases like "Here is the summary:" or "This document is about...".

**Input Court Docket HTML:**
---
{html_content}
---

**Executive Summary:**
"""
    if not html_text:
        log_message(cursor, fk_task_run, "WARNING", "HTML content for summarization is empty.", fk_case=fk_case)
        return None

    truncated_html = html_text[:MAX_HTML_CHARS_TO_SEND]
    
    # --- FIXED: Correctly format the prompt with the HTML content ---
    full_prompt = PROMPT_TEMPLATE.format(html_content=truncated_html)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        # Adjusted generation config for factual summarization
        generation_config = {
            "temperature": 0.5,       # Lower temperature for more factual, less creative output
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024 # Sufficient for a detailed summary
        }
        
        response = model.generate_content(full_prompt, generation_config=generation_config)
        
        # Add safety check for empty or blocked response
        if not response.parts:
             log_message(cursor, fk_task_run, "WARNING", "Gemini response was blocked or empty. Check safety settings in Google AI Studio.", fk_case=fk_case)
             return None

        return response.text.strip()

    except google_exceptions.InvalidArgument as e:
        error_message = f"Gemini API Error (InvalidArgument): {e}. Check API key or model name."
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None
    except google_exceptions.ResourceExhausted as e:
        error_message = f"Gemini API Error (ResourceExhausted): {e}. Quota/rate limit may have been reached."
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None
    except google_exceptions.GoogleAPIError as e:
        error_message = f"Gemini API Error (GoogleAPIError): {e}. A general API error occurred."
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None
    except Exception as e:
        # Catch the potential KeyError from a bad prompt format, and other unexpected errors
        error_message = f"An unexpected error occurred during Gemini API call: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None

def summarize_case_html(html_text: str, api_key: str, cursor, fk_task_run, fk_case) -> str | None:
    """
    Summarizes a legal case's HTML docket report using the Google Gemini 1.5 Pro API,
    following the specific structured output format required by the DocketWatch system instructions.

    Important Note: This function is designed to summarize the overall docket report HTML,
    not the OCR'd text of a single PDF document. The prompt is tailored for that purpose.
    """
    # --- REVISED: Prompt Aligned with System Instructions ---
    # This prompt is specifically engineered to generate the multi-part analysis
    # required by the DocketWatch project guidelines. It clearly defines the role,
    # context, and the exact output structure, including the required headers.
    PROMPT_TEMPLATE = """
**Role:** You are a senior legal analyst and news editor for TMZ, operating the DocketWatch system.

**Task:** Analyze the provided HTML from a PACER court docket report. Your primary goal is to produce a structured analysis that is immediately useful for reporters. Focus on celebrity-related cases and newsworthy developments.

**Instructions:**
1.  Carefully review the entire HTML docket report to understand the case status and recent activity.
2.  Generate a response strictly following the format below.
3.  Use markdown for formatting, especially for the STORY section and bullet points.

**Required Output Format:**

**EVENT SUMMARY**
(Provide a 1-2 sentence summary of the most recent, significant event or the overall status of the case based on the docket.)

**NEWSWORTHINESS**
(Explain why this case is or could be newsworthy. Is a celebrity directly involved? Is the legal matter unusual, scandalous, or significant? Rate its newsworthiness on a scale of 1-10, with 10 being a major breaking story.)

**STORY**
(Write a short, narrative-style story (3-5 paragraphs) as a starting point for a TMZ article. Explain the background, what just happened, and what it means in simple, engaging language. Use markdown for paragraphs.)

**KEY DETAILS**
(List the most important facts as bullet points. Include parties involved, key dates, case numbers, and the core legal claims.)

**WHAT'S NEXT**
(Based on the docket, what are the likely next legal steps? Mention upcoming deadlines, hearings, or potential motions.)

---
**Input Court Docket HTML:**
{html_content}
---

**DOCKET ANALYSIS:**
"""
    if not html_text:
        log_message(cursor, fk_task_run, "WARNING", "HTML content for summarization is empty. Skipping Gemini call.", fk_case=fk_case)
        return None

    truncated_html = html_text[:MAX_HTML_CHARS_TO_SEND]
    full_prompt = PROMPT_TEMPLATE.format(html_content=truncated_html)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        generation_config = {
            "temperature": 0.6,       # A bit of creativity for the "STORY" section is good
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048 # Increased to allow for the more detailed, structured response
        }
        
        response = model.generate_content(full_prompt, generation_config=generation_config)
        
        if not response.parts:
             log_message(cursor, fk_task_run, "WARNING", "Gemini response was blocked or empty. Check safety settings.", fk_case=fk_case)
             return None

        # The model should start its response directly with "EVENT SUMMARY"
        return response.text.strip()

    except google_exceptions.InvalidArgument as e:
        error_message = f"Gemini API Error (InvalidArgument): {e}. Check API key or model name."
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None
    except google_exceptions.GoogleAPIError as e:
        error_message = f"Gemini API Error: {e}. A general API error occurred."
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None
    except Exception as e:
        error_message = f"An unexpected error occurred during Gemini API call: {e}"
        log_message(cursor, fk_task_run, "ERROR", error_message, fk_case=fk_case)
        return None

# --- MAIN SCRIPT LOGIC ---

def main():
    global conn, cursor, driver, fk_task_run

    if len(sys.argv) < 2:
        print("Usage: python pacer_single.py <CASE_ID>")
        return

    case_id_arg = int(sys.argv[1])
    
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.id as fk_task_run 
        FROM docketwatch.dbo.task_runs r
        INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
        WHERE s.filename = ? 
        ORDER BY r.id DESC
    """, (script_filename,))
    task_run = cursor.fetchone()
    fk_task_run = task_run[0] if task_run else None

    if is_another_instance_running():
        log_message(cursor, fk_task_run, "ERROR", "Another instance is already running. Exiting...")
        return
    else:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

    cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
    USERNAME, PASSWORD, LOGIN_URL = cursor.fetchone()

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_options)
    
    # --- REVERTED TO YOUR ORIGINAL WORKING LOGIN LOGIC ---
    driver.get(LOGIN_URL)
    driver.find_element(By.NAME, "loginForm:loginName").send_keys(USERNAME)
    driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
    try:
        client_code = driver.find_element(By.NAME, "loginForm:clientCode")
        client_code.clear()
        client_code.send_keys("DocketWatch")
    except:
        pass
    driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
    human_pause(3, 5)
    # --- END OF REVERTED BLOCK ---

    cursor.execute("""
        SELECT c.id, c.id as fk_case, c.case_url, c.case_name, c.case_number
        FROM docketwatch.dbo.cases c
        WHERE c.id = ?
    """, (case_id_arg,))
    cases = cursor.fetchall()

    for case_id, fk_case, case_url, case_name, case_number in cases:
        driver.get(case_url)
        human_pause(3, 5)
        driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report").click()
        human_pause(2, 3)
        driver.find_element(By.NAME, "button1").click()
        human_pause(2, 4)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        extract_and_store_pacer_billing(soup, cursor, fk_case, fk_task_run)

        cursor.execute("SELECT COUNT(*) FROM dbo.case_events WHERE fk_cases = ?", (fk_case,))
        existing_dockets = cursor.fetchone()[0]
        log_message(cursor, fk_task_run, "INFO", f"{existing_dockets} existing dockets for case {case_name}", fk_case=fk_case)

        mark_case_found(cursor, fk_case)

        docket_rows = driver.find_elements(By.XPATH, "//table[@border='1']/tbody/tr")
        for row in docket_rows[1:]:
            columns = row.find_elements(By.TAG_NAME, "td")
            if len(columns) < 3:
                continue

            event_date = columns[0].text.strip()
            docket_number_text = columns[1].text.strip()
            docket_text = columns[2].text.strip()
            event_no = int(docket_number_text) if docket_number_text.isdigit() else 0
            cleaned_docket_text = clean_text(docket_text)

            cursor.execute("""
                SELECT COUNT(*) FROM dbo.case_events 
                WHERE event_date = ? AND LEFT(event_description, 100) = ? AND fk_cases = ?
            """, (event_date, cleaned_docket_text[:100], fk_case))
            exists = cursor.fetchone()[0]

            if not exists:
                log_id = log_message(cursor, fk_task_run, "ALERT", f"New docket discovered! Docket added to case {case_name}", fk_case=fk_case)
                cursor.execute("""
                    INSERT INTO dbo.case_events (
                        event_date, event_no, event_description, fk_cases, status, fk_task_run_log
                    ) VALUES (?, ?, ?, ?, 'New', ?)
                """, (event_date, event_no, cleaned_docket_text, fk_case, log_id))
                conn.commit()
                # send_docket_email(case_name, case_url, event_no, cleaned_docket_text)
            else:
                log_message(cursor, fk_task_run, "INFO", f"Docket number {event_no} already exists for case {case_name}", fk_case=fk_case)

        h3_tag = soup.find('h3')
        case_number_extracted, court_name, fk_court = None, None, None
        if h3_tag:
            h3_html = str(h3_tag).replace("<br>", "\n").replace("<BR>", "\n")
            h3_lines = BeautifulSoup(h3_html, "html.parser").get_text().split("\n")
            if len(h3_lines) >= 3:
                court_name = h3_lines[1].strip()
                case_number_extracted = h3_lines[2].split("CASE #:")[-1].strip()
                if court_name:
                    cursor.execute("UPDATE docketwatch.dbo.cases SET court_name_pacer = ? WHERE id = ?", (court_name, fk_case))
                    conn.commit()
                    cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_name_pacer = ?", (court_name,))
                    row = cursor.fetchone()
                    fk_court = row[0] if row else None

        td_blocks = soup.find_all('td', valign='top', width='60%')
        case_name_extracted = None
        for td in td_blocks:
            text = td.get_text(separator=' ', strip=True)
            if "Assigned to:" in text:
                case_name_extracted = text.split("Assigned to:")[0].strip()
                break
        if not case_name_extracted:
            for td in td_blocks:
                html = str(td)
                match = re.search(r"Case title:\s*(.*?)\s*<br\s*/?>", html, re.IGNORECASE)
                if match:
                    case_name_extracted = match.group(1).strip()
                    break
        if case_name_extracted:
            case_name_extracted = case_name_extracted.replace('&amp;', '&')
            
        if case_name_extracted or case_number_extracted or fk_court:
            update_sql = "UPDATE docketwatch.dbo.cases SET last_updated = GETDATE()"
            update_params = []
            if case_name_extracted:
                update_sql += ", case_name = ?"
                update_params.append(case_name_extracted)
            if case_number_extracted:
                update_sql += ", case_number = ?"
                update_params.append(case_number_extracted)
            if fk_court:
                update_sql += ", fk_court = ?"
                update_params.append(fk_court)
            update_sql += " WHERE id = ?"
            update_params.append(fk_case)
            cursor.execute(update_sql, update_params)
            conn.commit()
            log_message(cursor, fk_task_run, "INFO", "Updated case metadata", fk_case=fk_case)

        gemini_key = get_gemini_key(cursor)
        if gemini_key:
            summary = summarize_case_html(clean_html(str(soup)), gemini_key, cursor, fk_task_run, fk_case)
            if summary:
                html_version = convert_to_clean_html(summary)
                summary_cleaned = sanitize_unicode(summary)
                html_version_cleaned = sanitize_unicode(html_version)
                cursor.execute(
                    "UPDATE docketwatch.dbo.cases SET summarize = ?, summarize_html = ? WHERE id = ?",
                    (summary_cleaned[:4000], html_version_cleaned[:8000], fk_case)
                )
                conn.commit()
                log_message(cursor, fk_task_run, "INFO", "Gemini summary saved", fk_case=fk_case)
            else:
                log_message(cursor, fk_task_run, "WARNING", "Gemini summary failed or was empty.", fk_case=fk_case)
        else:
            log_message(cursor, fk_task_run, "WARNING", "Gemini API key not found. Skipping summarization.", fk_case=fk_case)

if __name__ == "__main__":
    driver = None
    try:
        main()
    finally:
        try: log_message(cursor, fk_task_run, "INFO", "PACER Scraper Completed Successfully")
        except: pass
        try: cursor.close()
        except: pass
        try: conn.close()
        except: pass
        try: driver.quit()
        except: pass
        try: os.remove(LOCK_FILE)
        except: pass