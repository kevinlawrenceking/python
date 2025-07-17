from scraper_base import extract_and_store_pacer_billing
import time
import pyodbc
import os
import sys
import logging
import psutil
import random
import unicodedata
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from scraper_base import mark_case_not_found
from scraper_base import mark_case_found
from scraper_base import log_message

FROM_EMAIL = "it@tmz.com"
TO_EMAILS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "marlee.chartash@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25


def send_docket_email(case_name, case_url, event_no, cleaned_docket_text):
    subject = f"DocketWatch Alert: {case_name} – New Docket Discovered"
    body = f"""
    <html>
    <body>
        A new docket has been detected for case:<br>
        <a href=\"{case_url}\">{case_name}</a><br><br>
        <strong>Docket No:</strong> {event_no}<br>
        <strong>Description:</strong><br>
        <p>{cleaned_docket_text}</p>
    </body>
    </html>
    """
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
        log_message(cursor, fk_task_run, "ERROR", f"Failed to send email for case {case_name}: {e}", fk_case=None)

LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\docketwatch_pacer_scraper_v2.log"
LOCK_FILE = r"\\10.146.176.84\general\docketwatch\python\docketwatch_pacer_scraper_v2.lock"
script_filename = os.path.splitext(os.path.basename(__file__))[0]

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def is_another_instance_running():
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "r") as f:
            try:
                pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    return True
            except ValueError:
                pass
        os.remove(LOCK_FILE)
    return False


def human_pause(min_time=1, max_time=3):
    time.sleep(random.uniform(min_time, max_time))


def clean_text(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text).replace("'", "''").replace("\n", " ").replace("\r", " ")
    return text[:4000]

def main():
    global conn, cursor, driver, fk_task_run

    if len(sys.argv) < 2:
        print("Usage: python docketwatch_pacer_scraper_v2.py <PRIORITY> [CASE_ID]")
        return

    try:
        PRIORITY_ARG = int(sys.argv[1])
    except ValueError:
        print("Invalid priority value. Must be an integer between 1 and 4.")
        return

    case_id_arg = None
    if len(sys.argv) > 2:
        try:
            case_id_arg = int(sys.argv[2])
            logging.info(f"Filtering for specific case ID: {case_id_arg}")
        except ValueError:
            logging.warning(f"Ignoring invalid case ID argument: {sys.argv[2]}")
            case_id_arg = None

    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        cursor = conn.cursor()
        logging.info("Database Connection Established")
    except Exception as e:
        logging.error(f"Database Connection Failed: {str(e)}")
        return

    cursor.execute("""
        SELECT r.id as fk_task_run 
        FROM docketwatch.dbo.task_runs r
        INNER JOIN docketwatch.dbo.scheduled_task s ON r.fk_scheduled_task = s.id 
        WHERE s.filename = ? 
        ORDER BY r.id DESC
    """, (script_filename,))
    task_run = cursor.fetchone()
    fk_task_run = task_run[0] if task_run else None

    # Put your custom startup log here
    if case_id_arg:
        log_message(cursor, fk_task_run, "INFO", f"=== PACER Scraper Started (Priority {PRIORITY_ARG}, Case ID {case_id_arg}) ===")
    else:
        log_message(cursor, fk_task_run, "INFO", f"=== PACER Scraper Started (Priority {PRIORITY_ARG}) ===")

    if is_another_instance_running():
        log_message(cursor, fk_task_run, "ERROR", "Another instance is already running. Exiting...")
        return
    else:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

    try:
        cursor.execute("SELECT username, pass, login_url FROM dbo.tools WHERE id = 2")
        row = cursor.fetchone()
        if not row:
            log_message(cursor, fk_task_run, "ERROR", "PACER credentials not found in the database.")
            return
        USERNAME, PASSWORD, LOGIN_URL = row
        log_message(cursor, fk_task_run, "INFO", "PACER credentials retrieved successfully")
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Error retrieving PACER credentials: {str(e)}")
        return

    try:
        CHROMEDRIVER_PATH = "C:/WebDriver/chromedriver.exe"
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-dev-shm-usage")
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        log_message(cursor, fk_task_run, "INFO", "ChromeDriver Initialized Successfully")
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"ChromeDriver Initialization Failed: {str(e)}")
        return

    try:
        driver.get(LOGIN_URL)
        human_pause(2, 4)

        driver.find_element(By.NAME, "loginForm:loginName").send_keys(USERNAME)
        human_pause(1, 2)

        driver.find_element(By.NAME, "loginForm:password").send_keys(PASSWORD)
        human_pause(1, 2)

        # Fill in Client Code
        try:
            client_code_input = driver.find_element(By.NAME, "loginForm:clientCode")
            client_code_input.clear()
            client_code_input.send_keys("DocketWatch")
            human_pause(1, 2)
            log_message(cursor, fk_task_run, "INFO", "Client Code 'DocketWatch' entered successfully.")
        except Exception as e:
            log_message(cursor, fk_task_run, "WARNING", f"Client Code field not found or could not be filled: {e}")

        driver.find_element(By.NAME, "loginForm:fbtnLogin").click()
        human_pause(3, 5)

        log_message(cursor, fk_task_run, "INFO", "PACER login successful.")
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"PACER login failed: {str(e)}")
        return

    try:
        if case_id_arg:
            cursor.execute("""
                SELECT c.id, c.id as fk_case, c.case_url, c.case_name, c.case_number
                FROM docketwatch.dbo.cases c
                WHERE c.fk_tool = 2 AND c.case_url IS NOT NULL and c.status = 'Tracked'
                AND c.id = ?
            """, (case_id_arg,))
        else:
            cursor.execute("""
                  SELECT c.id, c.id as fk_case, c.case_url, c.case_name, c.case_number
                FROM docketwatch.dbo.cases c
				INNER join docketwatch.dbo.courts crt on crt.court_code = c.fk_court
				INNER join docketwatch.dbo.pacer_sites p on p.url = crt.pacer_url
                WHERE c.fk_tool = 2 AND c.case_url IS NOT NULL and c.status = 'Tracked'
				AND p.isRSS = 0 AND c.fk_priority = ?
            """, (PRIORITY_ARG,))
        cases = cursor.fetchall()
        log_message(cursor, fk_task_run, "INFO", f"Queried {len(cases)} case(s) to review", fk_case=None)

        if not cases:
            log_message(cursor, fk_task_run, "WARNING", "No tracked cases found for PACER. Exiting...")
            return
    except Exception as e:
        log_message(cursor, fk_task_run, "ERROR", f"Database query for cases failed: {str(e)}")
        return

    for case in cases:
        case_id, fk_case, case_url, case_number, case_name = case
        log_id = log_message(cursor, fk_task_run, "INFO", f"Reviewing case: {case_name}", fk_case=fk_case)
        cursor.execute("UPDATE dbo.cases SET fk_task_run_log = ? WHERE id = ?", (log_id, case_id))
        conn.commit()

        try:
            driver.get(case_url)
            human_pause(3, 5)
        except Exception as e:
            log_message(cursor, fk_task_run, "ERROR", f"Failed to load case URL: {case_url} – {e}", fk_case=fk_case)
            mark_case_not_found(cursor, fk_case, fk_task_run)  # <--- add this line
            continue

        driver.find_element(By.PARTIAL_LINK_TEXT, "Docket Report").click()
        human_pause(3, 5)

        date_format = "%m/%d/%Y"
        date_from_str = (datetime.today() - timedelta(days=5)).strftime(date_format)
        date_to_str = (datetime.today() + timedelta(days=5)).strftime(date_format)
        log_message(cursor, fk_task_run, "INFO", f"Setting date range: FROM {date_from_str} TO {date_to_str}", fk_case=fk_case)

        driver.find_element(By.XPATH, '//input[@name="date_range_type" and @value="Filed"]').click()
        driver.find_element(By.NAME, "date_from").clear()
        driver.find_element(By.NAME, "date_from").send_keys(date_from_str)
        driver.find_element(By.NAME, "date_to").clear()
        driver.find_element(By.NAME, "date_to").send_keys(date_to_str)

        for checkbox_id in ["list_of_parties_and_counsel", "terminated_parties"]:
            try:
                checkbox = driver.find_element(By.ID, checkbox_id)
                if checkbox.is_selected():
                    checkbox.click()
                    log_message(cursor, fk_task_run, "INFO", f"Unchecked checkbox: {checkbox_id}", fk_case=fk_case)
            except Exception as e:
                log_message(cursor, fk_task_run, "WARNING", f"Checkbox {checkbox_id} not found or error: {e}", fk_case=fk_case)

        try:
            Select(driver.find_element(By.NAME, "sort1")).select_by_visible_text("Most recent date first")
        except Exception as e:
            log_message(cursor, fk_task_run, "WARNING", f"Sort dropdown not found: {e}", fk_case=fk_case)

        human_pause(1, 2)
        driver.find_element(By.NAME, "button1").click()
        human_pause(3, 5)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        extract_and_store_pacer_billing(soup, cursor, fk_case, fk_task_run)


        # Extract case information from the h3 tag
        h3_tag = soup.find('h3')
        case_number_extracted = None
        court_name = None
        fk_court = None

        if h3_tag:
            log_message(cursor, fk_task_run, "INFO", f"Found <h3> tag: {h3_tag.get_text(strip=True)[:120]}...", fk_case=fk_case)
            # Convert the <br> tags to newlines and extract lines
            h3_html = str(h3_tag).replace("<br>", "\n").replace("<BR>", "\n")
            h3_lines = BeautifulSoup(h3_html, "html.parser").get_text().split("\n")

            log_message(cursor, fk_task_run, "INFO", f"h3_lines parsed: {h3_lines}", fk_case=fk_case)

            # Extract from expected line positions
            if len(h3_lines) >= 3:
                court_name = h3_lines[1].strip()
                case_number_extracted = h3_lines[2].split("CASE #:")[-1].strip()

                log_message(cursor, fk_task_run, "INFO", f"Extracted court: {court_name}", fk_case=fk_case)
                log_message(cursor, fk_task_run, "INFO", f"Extracted case number: {case_number_extracted}", fk_case=fk_case)

                if court_name:
                    cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_name = ?", (court_name,))
                    row = cursor.fetchone()
                    if row:
                        fk_court = row[0]
                        log_message(cursor, fk_task_run, "INFO", f"Matched existing court_code: {fk_court}", fk_case=fk_case)
                    else:
                        log_message(cursor, fk_task_run, "WARNING", f"No match found for court name: {court_name}. Skipping court assignment.", fk_case=fk_case)

            else:
                log_message(cursor, fk_task_run, "WARNING", f"Unexpected h3 format: fewer than 3 lines found – raw h3 lines: {h3_lines}", fk_case=fk_case)
        else:
            log_message(cursor, fk_task_run, "WARNING", "No <h3> tag found on page — cannot extract court or case number", fk_case=fk_case)

        # Extract case name
        td_blocks = soup.find_all('td', valign='top', width='60%')
        case_name_extracted = None

        # First try "Assigned to:"
        for td in td_blocks:
            text = td.get_text(separator=' ', strip=True)
            log_message(cursor, fk_task_run, "DEBUG", f"Inspecting <td>: {text[:120]}...", fk_case=fk_case)
            if "Assigned to:" in text:
                case_name_extracted = text.split("Assigned to:")[0].strip()
                log_message(cursor, fk_task_run, "INFO", f"Extracted case name from 'Assigned to': {case_name_extracted}", fk_case=fk_case)
                break

        # Fallback: use regex to cleanly extract after "Case title:" and before <br>
        if not case_name_extracted:
            for td in td_blocks:
                html = str(td)
                match = re.search(r"Case title:\s*(.*?)\s*<br\s*/?>", html, re.IGNORECASE)
                if match:
                    case_name_extracted = match.group(1).strip()
                    log_message(cursor, fk_task_run, "INFO", f"Case title fallback used via regex: {case_name_extracted}", fk_case=fk_case)
                    break

        if case_name_extracted:
            case_name_extracted = case_name_extracted.replace('&amp;', '&')

        log_message(cursor, fk_task_run, "INFO", f"Scraped Name/Number: {case_name_extracted} / {case_number_extracted}", fk_case=fk_case)

        if case_name_extracted and case_number_extracted:
            cursor.execute("UPDATE docketwatch.dbo.cases SET case_name = ?, last_updated = GETDATE(), case_number = ? WHERE id = ?",
                        (case_name_extracted, case_number_extracted, fk_case))
            conn.commit()

            if fk_court:
                cursor.execute("UPDATE docketwatch.dbo.cases SET fk_court = ?, last_updated = GETDATE() WHERE id = ?", (fk_court, fk_case))
                conn.commit()
                log_message(cursor, fk_task_run, "INFO", f"Updated fk_court for case ID {fk_case}", fk_case=fk_case)
            log_message(cursor, fk_task_run, "INFO", f"Updated case_name and case_number for case ID {fk_case}", fk_case=fk_case)
        else:
            log_message(cursor, fk_task_run, "WARNING", f"Could not extract case name or number for case ID {fk_case}", fk_case=fk_case)
            mark_case_not_found(cursor, fk_case, fk_task_run)

        # Get existing dockets for the case
        cursor.execute("SELECT COUNT(*) FROM dbo.case_events WHERE fk_cases = ?", (fk_case,))
        existing_dockets = cursor.fetchone()[0]
        log_message(cursor, fk_task_run, "INFO", f"{existing_dockets} existing dockets for case {case_name_extracted or case_name}", fk_case=fk_case)

        mark_case_found(cursor, fk_case)  # <-- Reset not_found state!

        # Process docket rows
        docket_rows = driver.find_elements(By.XPATH, "//table[@border='1']/tbody/tr")
        for row in docket_rows[1:]:  # Skip header row
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
                send_docket_email(case_name, case_url, event_no, cleaned_docket_text)
            else:
                log_message(cursor, fk_task_run, "INFO", f"Docket number {event_no} already exists for case {case_name}", fk_case=fk_case)


if __name__ == "__main__":
    driver = None
    try:
        main()
    finally:
        try:
            log_message(cursor, fk_task_run, "INFO", "PACER Scraper Completed Successfully")
        except:
            pass
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        try:
            if driver:
                driver.quit()
        except:
            pass
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except:
            pass
