# docketwatch_broward_scraper.py
# Refactored to use scraper_base.py utilities

import os
import sys
import time
import traceback
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scraper_base import (
    setup_logging, get_db_cursor, get_task_context, log_message,
    update_case_records, insert_new_case_events,
    extract_case_name_from_html, extract_court_and_type,
    DEFAULT_CHROMEDRIVER_PATH, init_logging_and_filename,
    dispatch_case_loop, log_insert_result, log_no_events_table,
    perform_tool_login
)

# Set constants
CHROMEDRIVER_PATH = DEFAULT_CHROMEDRIVER_PATH
script_filename = init_logging_and_filename()

def insert_case_events(driver, fk_case, case_name, tool_case_number, cursor, fk_task_run):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    event_table = soup.find("table", {"id": "tblEvents"})
    if not event_table:
        log_no_events_table(cursor, fk_task_run, tool_case_number)
        return

    events = []
    for row in event_table.find("tbody").find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        event_date = cols[0].text.strip()
        description = cols[1].text.strip()
        extra = cols[2].text.strip()
        full_description = f"{description} | {extra}" if extra else description
        events.append((event_date, full_description, extra))

    inserted = insert_new_case_events(cursor, fk_case, events, fk_task_run)
    log_insert_result(cursor, fk_task_run, case_name, inserted)

def update_case_and_tool_case(driver, cursor, fk_task_run, TOOL_ID, case_id, case_number, search_url, fk_county):
    try:
        log_message(cursor, fk_task_run, "INFO", f"Opening: {search_url.strip()}")
        driver.get(search_url.strip())
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="#caseNumberSearch"]'))).click()
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "CaseNumber"))).send_keys(case_number)
        driver.find_element(By.ID, "CaseNumberSearchResults").click()
        time.sleep(5)

        viewer_elements = driver.find_elements(By.CLASS_NAME, "bc-casedetail-viewer")
        if not viewer_elements:
            log_message(cursor, fk_task_run, "INFO", f"No case detail viewer found for case {case_number}. Skipping.")
            print(f"SKIPPED: No viewer for case {case_number}")
            return
        viewer_elements[0].click()
        time.sleep(5)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        case_name = extract_case_name_from_html(page_source)
        fk_court, case_type = extract_court_and_type(soup, fk_county, cursor)

        update_case_records(cursor, case_id, case_number, case_name, TOOL_ID, fk_court, case_type, fk_task_run, driver.current_url)
        insert_case_events(driver, case_id, case_name, case_number, cursor, fk_task_run)
        print(f"UPDATED_CASE_ID={case_id}")

    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Error updating case {case_id}: {e}")
        traceback.print_exc()

def main():
    print("MAIN() IS RUNNING")

    try:
        conn, cursor = get_db_cursor()
    except Exception as db_err:
        print("DB connect failed:", db_err)
        exit()

    print("Database connection successful")
    print("Script filename is:", script_filename)

    context = get_task_context(cursor, script_filename)
    if not context:
        print("ERROR: No scheduled_task/tool record found for this script.")
        return

    print("fk_task_run is:", context['fk_task_run'])
    TOOL_ID = context['tool_id']

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

    try:
        if context["is_login"]:
            perform_tool_login(driver, context)
        else:
            log_message(cursor, context["fk_task_run"], "INFO", "No login required for this tool.")

        driver.get(context["search_url"])
        dispatch_case_loop(cursor, TOOL_ID, context["fk_task_run"], script_filename, driver, update_case_and_tool_case)

    except Exception as e:
        print("Fatal error:", e)
        log_message(cursor, context["fk_task_run"], "ERROR", f"Fatal error: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
