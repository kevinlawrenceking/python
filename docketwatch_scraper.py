# docketwatch_scraper.py
# Universal dynamic scraper using refactored scraper_base + tool config
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
from scraper_base import mark_case_not_found, mark_case_found

from scraper_base import (
    get_db_cursor, get_tool_selectors,
    perform_tool_login, DEFAULT_CHROMEDRIVER_PATH,
    log_message, update_case_records, insert_new_case_events,
    extract_case_name_from_html, extract_court_and_type, get_task_context_by_tool_id, setup_logging
)

CHROMEDRIVER_PATH = DEFAULT_CHROMEDRIVER_PATH
script_filename = os.path.splitext(os.path.basename(sys.argv[0]))[0]
TOOL_ID = int(sys.argv[1]) if len(sys.argv) > 1 else None
SINGLE_CASE_ID = int(sys.argv[2]) if len(sys.argv) > 2 else None

def update_case(driver, cursor, fk_task_run, TOOL_ID, case_id, case_number, tool,
                default_case_name=None, default_fk_court=None, default_case_type=None):
    try:
        log_message(cursor, fk_task_run, "INFO", f"Opening: {tool['search_url']}", fk_case=case_id)
        driver.get(tool["search_url"])
        time.sleep(2)
        log_message(cursor, fk_task_run, "INFO", "Initial page load complete", fk_case=case_id)

        # === CAPTCHA Handling (reCAPTCHA v2) ===
        if tool.get("captcha_type") == "recaptcha_v2":
            try:
                input_selector = tool.get("captcha_input_selector") or "#g-recaptcha-response"
                submit_selector = tool.get("captcha_submit_selector") or tool.get("search_button_selector")

                # Wait for reCAPTCHA iframe to appear
                iframe = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha']"))
                )

                # Extract sitekey from iframe src
                iframe_src = iframe.get_attribute("src")
                import urllib.parse
                parsed = urllib.parse.urlparse(iframe_src)
                site_key = urllib.parse.parse_qs(parsed.query).get("k", [None])[0]

                if not site_key:
                    raise Exception("Could not extract sitekey from reCAPTCHA iframe URL")

                current_url = driver.current_url

                # Get 2Captcha API key
                cursor.execute("SELECT captcha_api FROM docketwatch.dbo.utilities WHERE id = 1")
                api_row = cursor.fetchone()
                if not api_row or not api_row[0]:
                    raise Exception("Missing 2Captcha API key")

                from scraper_base import solve_recaptcha_2captcha
                token = solve_recaptcha_2captcha(api_row[0], site_key, current_url)

                # Force visibility, inject token, and wait long enough for reCAPTCHA to process it
                driver.execute_script(f"""
                    let recaptcha = document.querySelector("{input_selector}");
                    if (recaptcha) {{
                        recaptcha.style.display = 'block';
                        recaptcha.style.width = '300px';
                        recaptcha.style.height = '100px';
                        recaptcha.style.opacity = '1';
                        recaptcha.value = "{token}";
                        recaptcha.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                """)
                time.sleep(8)

                # === PAUSE FOR REMOTE DEBUGGING ===
                log_message(cursor, fk_task_run, "INFO", "PAUSING FOR DEBUGGING — browser open", fk_case=case_id)
                time.sleep(999)

                if submit_selector:
                    try:
                        search_btn = driver.find_element(By.CSS_SELECTOR, submit_selector)
                        driver.execute_script("arguments[0].disabled = false;", search_btn)
                        log_message(cursor, fk_task_run, "INFO", "CAPTCHA solved and submit button re-enabled.", fk_case=case_id)
                    except Exception as e:
                        log_message(cursor, fk_task_run, "WARNING", f"Submit button not found or failed to enable: {e}", fk_case=case_id)

            except Exception as e:
                log_message(cursor, fk_task_run, "ERROR", f"Failed to solve reCAPTCHA: {e}", fk_case=case_id)
                return

        if tool.get("pre_search_click_selector"):
            try:
                driver.find_element(By.CSS_SELECTOR, tool["pre_search_click_selector"]).click()
                time.sleep(1)
            except Exception as e:
                log_message(cursor, fk_task_run, "WARNING", f"Pre-search click failed: {e}", fk_case=case_id)

        log_message(cursor, fk_task_run, "INFO", "Waiting for case number input field...", fk_case=case_id)
        input_field = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, tool["case_number_input"]))
        )
        input_field.clear()
        input_field.send_keys(case_number)

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, tool["search_button_selector"]))
        ).click()

        viewer_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, tool["result_row_selector"]))
        )
        if not viewer_elements:
            log_message(cursor, fk_task_run, "INFO", f"No result rows found for case {case_number}. Skipping.", fk_case=case_id)
            return

        try:
            viewer_elements[0].click()
            log_message(cursor, fk_task_run, "INFO", "Clicked into case detail.", fk_case=case_id)
            time.sleep(2)
        except Exception as e:
            log_message(cursor, fk_task_run, "ERROR", f"Failed to click result row: {e}", fk_case=case_id)
            mark_case_not_found(cursor, case_id, fk_task_run)
            return

        if TOOL_ID != 15:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, tool["events_table_selector"]))
                )
            except Exception:
                log_message(cursor, fk_task_run, "INFO", f"Events table never appeared for case {case_number}", fk_case=case_id)
                return

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        case_name = extract_case_name_from_html(page_source, tool.get("case_name_selector")) or default_case_name
        fk_court, case_type = extract_court_and_type(soup, tool.get("fk_county"), cursor)
        fk_court = fk_court or default_fk_court
        case_type = case_type or default_case_type

        update_case_records(cursor, case_id, case_number, case_name, TOOL_ID, fk_court, case_type, fk_task_run, driver.current_url)
        mark_case_found(cursor, case_id)

        events = []

        if TOOL_ID == 15:
            event_blocks = soup.select("div.portal-case-event")
            for block in event_blocks:
                try:
                    date_line = block.select_one("p.text-primary").get_text(" ", strip=True)
                    date_text = date_line[:10]
                    description = date_line[10:].strip()

                    comment_block = next((p for p in block.find_all("p") if p.find("span", class_="text-muted")), None)
                    extra_text = comment_block.get_text(strip=True).split("]", 1)[-1].strip() if comment_block else ""

                    doc_tag = block.select_one("[data-doc-docname]")
                    if doc_tag:
                        extra_text = doc_tag["data-doc-docname"]

                    events.append((date_text, description, extra_text))
                except Exception as e:
                    log_message(cursor, fk_task_run, "WARNING", f"Failed to extract Clark event block: {e}", fk_case=case_id)
        else:
            table = soup.select_one(tool["events_table_selector"])
            if not table:
                log_message(cursor, fk_task_run, "WARNING", f"Events table not found in parsed HTML for case {case_number}", fk_case=case_id)
                return

            rows = table.select("tbody tr")
            col_count = int(tool.get("events_column_count") or 3)
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < col_count:
                    continue
                values = []
                for col in cols[:3]:
                    link = col.find("a")
                    if link and "dDescription" in link.get("class", []):
                        values.append(link.get_text(strip=True))
                    else:
                        values.append(col.get_text(strip=True))
                events.append((values[0], values[1], values[2]))

        inserted = insert_new_case_events(cursor, case_id, events, fk_task_run)
        log_message(cursor, fk_task_run, "ALERT" if inserted else "INFO", f"Inserted {inserted} event(s) for {case_name}", fk_case=case_id)

    except Exception as e:
        err_details = traceback.format_exc()
        log_message(cursor, fk_task_run, "ERROR", f"Error updating case {case_id}: {str(e)}\n{err_details}", fk_case=case_id)

def main():
    if not TOOL_ID:
        print("Usage: python docketwatch_scraper.py <TOOL_ID> [CASE_ID]")
        return

    conn, cursor = get_db_cursor()
    context = get_task_context_by_tool_id(cursor, TOOL_ID)
    if not context:
        print(f"ERROR: Could not resolve task context for TOOL_ID {TOOL_ID}.")
        return

    setup_logging(rf"\\10.146.176.84\general\docketwatch\python\logs\{context['logfile_name']}")
    selectors = get_tool_selectors(cursor, context["tool_id"])

    options = Options()
   ## options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
        log_message(cursor, context["fk_task_run"], "INFO", "Chrome launched successfully.")
    except Exception as e:
        log_message(cursor, context["fk_task_run"], "ERROR", f"ChromeDriver launch failed: {e}")
        traceback.print_exc()
        return

    try:
        if context["is_login"]:
            perform_tool_login(driver, context)
        else:
            log_message(cursor, context["fk_task_run"], "INFO", "No login required for this tool.")

        if SINGLE_CASE_ID:
            cursor.execute("""
                SELECT 
                    c.case_number, 
                    c.case_name, 
                    c.fk_court, 
                    c.case_type 
                FROM docketwatch.dbo.cases c 
                WHERE c.id = ?
            """, (SINGLE_CASE_ID,))
            row = cursor.fetchone()
            if not row:
                print(f"ERROR: Case ID {SINGLE_CASE_ID} not found.")
                return

            update_case(driver, cursor, context["fk_task_run"], TOOL_ID, SINGLE_CASE_ID,
                        row[0], selectors, row[1], row[2], row[3])
        else:
            cursor.execute("""
                SELECT 
                    c.id, 
                    c.case_number, 
                    c.case_name, 
                    c.fk_court, 
                    c.case_type 
                FROM docketwatch.dbo.cases c
 
                WHERE c.status = 'Tracked' AND c.fk_tool = ?
            """, (TOOL_ID,))
            rows = cursor.fetchall()

            log_message(cursor, context["fk_task_run"], "INFO", f"Processing {len(rows)} tracked case(s).")

            for row in rows:
                log_message(cursor, context["fk_task_run"], "INFO", f"Processing case ID {row[0]} ({row[1]})", fk_case=row[0])
                update_case(driver, cursor, context["fk_task_run"], TOOL_ID,
                            row[0], row[1], selectors, row[2], row[3], row[4])
                time.sleep(2)

    finally:
        driver.quit()
        log_message(cursor, context["fk_task_run"], "INFO", "Scraper completed and resources closed.")
        cursor.close()
        conn.close()      

if __name__ == "__main__":
    main()
