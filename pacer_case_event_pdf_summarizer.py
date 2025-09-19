"""
PACER Case Summarizer

- Logs into PACER using custom login method
- Navigates to each case URL and clicks into full docket report
- Ensures 'list_of_parties_and_counsel' is checked, 'terminated_parties' is unchecked
- Extracts HTML of full docket page (no date filtering)
- Sends to Gemini for summarization
- Saves result to cases.summarize and cases.summarize_html
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
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from scraper_base import (
    get_db_cursor,
    get_task_context_by_tool_id,
    log_message,
    DEFAULT_CHROMEDRIVER_PATH,
)

# Note: Removed pyodbc.setdecoding calls as they don't exist in current pyodbc version


def human_pause(a, b):
    time.sleep((a + b) / 2)


def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


PROMPT_TEMPLATE = """
You are a legal analyst for a major entertainment news organization. Create a clear, professional summary that helps journalists understand and report on this case.

Analyze the following case and docket data to extract:

* The case name, case number, jurisdiction, and presiding judge.
* The parties involved, including plaintiffs, defendants, and others.
* A clear chronological narrative summarizing key filings, hearings, motions, rulings, and milestones. Include docket numbers when relevant.
* Any unusual or notable filings.
* The current status of the case.
* Related case numbers or consolidations if noted.

Close with a short section titled "Why It Matters", explaining the case’s potential relevance to the entertainment industry, public interest, or legal precedent.

Neutral language. Do not guess. State clearly if information is missing.

Keep under 800 words.

Below is the case docket data:
"""

MAX_INPUT_LENGTH = 16000


def clean_html(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.get_text().split())


def convert_to_clean_html(summary_text):
    html = markdown2.markdown(summary_text)
    soup = BeautifulSoup(html, "html.parser")
    return str(soup)


def get_target_cases(cursor, single_case_id=None):
    if single_case_id:
        cursor.execute(
            """
            SELECT
                c.id,
                c.id AS fk_case,
                CAST(c.case_number AS NVARCHAR(MAX)) AS case_number,
                CAST(c.case_name   AS NVARCHAR(MAX)) AS case_name,
                CAST(c.case_url    AS NVARCHAR(MAX)) AS case_url
            FROM docketwatch.dbo.cases c
            WHERE c.id = ?
            """,
            (single_case_id,),
        )
    else:
        cursor.execute(
            """
            SELECT DISTINCT
                c.id,
                c.id AS fk_case,
                CAST(c.case_number AS NVARCHAR(MAX)) AS case_number,
                CAST(c.case_name   AS NVARCHAR(MAX)) AS case_name,
                CAST(c.case_url    AS NVARCHAR(MAX)) AS case_url,
                CAST(d.summary_ai  AS NVARCHAR(MAX)) AS doc_summary,
                CAST(e.summarize   AS NVARCHAR(MAX)) AS event_summary,
                CAST(c.summarize   AS NVARCHAR(MAX)) AS case_summary,
                d.date_downloaded
            FROM docketwatch.dbo.cases c
            INNER JOIN docketwatch.dbo.case_events e ON e.fk_cases = c.id
            INNER JOIN docketwatch.dbo.documents d   ON d.fk_case_event = e.id
            WHERE c.case_number <> 'Unfiled'
              AND d.summary_ai IS NULL
              AND c.summarize IS NOT NULL
              AND c.fk_tool = 2
              AND d.rel_path IS NOT NULL
            ORDER BY d.date_downloaded DESC
            """
        )
    return cursor.fetchall()


def summarize_case_html(html_text, api_key):
    prompt = PROMPT_TEMPLATE + html_text[:MAX_INPUT_LENGTH]
    models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

    for model in models:
        for attempt in range(3):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "contents": [
                                {"role": "user", "parts": [{"text": prompt}]}
                            ],
                            "generationConfig": {
                                "temperature": 0.6,
                                "max_output_tokens": 1000,
                            },
                        }
                    ),
                )
                result = r.json()
                if r.status_code == 200 and result.get("candidates"):
                    return (
                        result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    )
                if r.status_code == 503:
                    time.sleep((attempt + 1) * 10)
                    continue
                break
            except Exception:
                if attempt < 2:
                    time.sleep(5)
    return None


def login_to_pacer(driver, username, password, cursor, fk_task_run):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", type=int)
    args = parser.parse_args()

    conn, cursor = get_db_cursor()
    context = get_task_context_by_tool_id(cursor, 2)
    gemini_key = get_gemini_key(cursor)
    username = context.get("username")
    password = context.get("pass")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(DEFAULT_CHROMEDRIVER_PATH), options=options
    )

    try:
        login_to_pacer(driver, username, password, cursor, context["fk_task_run"])
        cases = get_target_cases(cursor, args.case_id)

        for case_row in cases:
            case_id, fk_case, case_number, case_name, case_url = case_row[:5]

            case_name_safe = str(case_name) if case_name else "Unknown"
            case_url_safe = str(case_url) if case_url else ""

            print(f"Processing: {case_number} - {case_name_safe}")

            driver.get(case_url_safe)
            human_pause(3, 5)

            driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report").click()
            human_pause(2, 3)

            try:
                cb = driver.find_element(By.ID, "list_of_parties_and_counsel")
                if not cb.is_selected():
                    cb.click()
            except:
                pass

            try:
                cb = driver.find_element(By.ID, "terminated_parties")
                if cb.is_selected():
                    cb.click()
            except:
                pass

            try:
                Select(driver.find_element(By.NAME, "sort1")).select_by_visible_text(
                    "Most recent date first"
                )
            except:
                pass

            driver.find_element(By.NAME, "button1").click()
            human_pause(3, 5)

            html = driver.page_source
            clean_text = clean_html(html)
            summary = summarize_case_html(clean_text, gemini_key)

            if summary:
                html_version = convert_to_clean_html(summary)
                cursor.execute(
                    "UPDATE docketwatch.dbo.cases SET summarize=?, summarize_html=? WHERE id=?",
                    (summary[:4000], html_version[:8000], case_id),
                )
                conn.commit()
            else:
                print("No summary returned.")

    finally:
        driver.quit()
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
