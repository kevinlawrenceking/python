import os
import pyodbc
import json
from datetime import datetime
from map_case_json import generate_and_save_map_summary

LOG_PATH = "U:\\docketwatch\\python\\logs\\map_summary_batch.log"

def log_line(text):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {text}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_db_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn, conn.cursor()

def get_gemini_key(cursor):
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    return row[0] if row else None

def main():
    conn, cursor = get_db_cursor()
    gemini_key = get_gemini_key(cursor)

    if not gemini_key:
        log_line("[!] No Gemini API key found. Exiting.")
        return

    cursor.execute("""
        SELECT top 5 id, id as fk_case, case_number, case_name, case_json
        FROM docketwatch.dbo.cases
        WHERE case_json IS NOT NULL AND summarize IS NULL
    """)
    rows = cursor.fetchall()

    log_line(f"Found {len(rows)} case(s) needing summary.")
    success_count = 0
    fail_count = 0

    for row in rows:
        fk_case = row.fk_case
        case_number = row.case_number
        case_name = row.case_name
        try:
            map_case_data = json.loads(row.case_json)
        except Exception as e:
            log_line(f"[!] Failed to parse JSON for case {case_number} ({case_name}): {e}")
            fail_count += 1
            continue

        result = generate_and_save_map_summary(cursor, conn, fk_case, case_number, case_name, map_case_data, gemini_key)
        if result:
            success_count += 1
        else:
            fail_count += 1

    log_line(f"[✓] Completed. Success: {success_count}, Failed: {fail_count}")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
