import sys
import requests
import pyodbc
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
import re

fk_task_run = 9999  # Replace with dynamic task run ID in prod

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        crt.court_code,
        crt.pacer_url,
        ft.url_suffix
    FROM docketwatch.dbo.courts crt
    LEFT JOIN docketwatch.dbo.feed_types ft ON crt.fk_feed_type = ft.id
    WHERE crt.pacer_url IS NOT NULL AND crt.pacer_status = 1
""")
sites = cursor.fetchall()

for court_code, base_url, url_suffix in sites:
    try:
        rss_url = base_url.rstrip("/") + (url_suffix or "/cgi-bin/rss_outside.pl")
        print(f"\nChecking RSS feed for: {rss_url}")

        response = requests.get(rss_url, timeout=10)
        if response.status_code != 200:
            print(f"   WARNING: {response.status_code} from {rss_url}")
            continue

        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} entries")

        for item in items:
            title = item.title.text.strip() if item.title else ""
            case_number, case_name = title.split(" ", 1) if " " in title else ("", title)

            pub_date = parsedate_to_datetime(item.pubDate.text.strip()) if item.pubDate else None
            guid = item.guid.text.strip() if item.guid else None
            link = item.link.text.strip() if item.link else None

            desc_raw = item.description.text.strip() if item.description else ""
            match = re.search(r'\[(.*?)\]', desc_raw)
            event_description = match.group(1) if match else None

            match_no = re.search(r'>(\d+)</a>', desc_raw)
            event_no = int(match_no.group(1)) if match_no else None

            # Check if GUID already exists
            cursor.execute("SELECT id FROM docketwatch.dbo.[rss_feed_entries] WHERE guid = ?", (guid,))
            if cursor.fetchone():
                continue  # Already exists

            # Insert new entry
            cursor.execute("""
                INSERT INTO docketwatch.dbo.[rss_feed_entries] (
                    fk_court, case_number, case_name, event_description, 
                    event_no, pub_date, guid, link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                court_code, case_number, case_name, event_description,
                event_no, pub_date, guid, link
            ))
            conn.commit()

    except Exception as e:
        print(f"   ERROR: {e}")

cursor.close()
conn.close()
