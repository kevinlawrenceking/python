import requests
from bs4 import BeautifulSoup
import urllib.parse
import pyodbc
import logging
import os

# === LOGGING SETUP ===
script_filename = os.path.splitext(os.path.basename(__file__))[0]
LOG_FILE = rf"\\10.146.176.84\general\docketwatch\python\logs\{script_filename}.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === DATABASE CONNECTION ===
DSN = "Docketwatch"
conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
cursor = conn.cursor()

# === 1. QUERY CASES WITHOUT LINKS ===
cursor.execute("""
    SELECT id, case_name
    FROM docketwatch.dbo.cases 
    WHERE id NOT IN (SELECT fk_case FROM docketwatch.dbo.case_links) 
    AND status = 'Tracked'
""")
cases = cursor.fetchall()
logging.info(f"Found {len(cases)} unlinked tracked cases.")

# === 2. FORMAT & BUILD SEARCH URL ===
def format_case_name(case_name):
    return urllib.parse.quote_plus(case_name)

def build_search_url(case_name):
    return f"https://www.tmz.com/search/?q={format_case_name(case_name)}"


# === 3. SCRAPE TMZ SEARCH RESULTS ===
def scrape_tmz_search_results(case_id, case_name):
    search_url = build_search_url(case_name)
    try:
        response = requests.get(search_url)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Request failed for case {case_id} - {case_name}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    cards = soup.select("article.gridler__card")

    results = []
    for card in cards:
        try:
            link_tag = card.select_one("a.gridler__card-link")
            title_tag = card.select_one("h4.gridler__card-title")
            img_tag = card.select_one("img")

            if link_tag and title_tag and img_tag:
                results.append({
                    "fk_case": case_id,
                    "case_url": link_tag['href'],
                    "title": title_tag.get_text(strip=True),
                    "image_url": img_tag['src']
                })
        except Exception as parse_err:
            logging.warning(f"Failed to parse article for case {case_id}: {parse_err}")

    return results


# === 4. INSERT INTO case_links TABLE ===
insert_sql = """
    INSERT INTO docketwatch.dbo.case_links (fk_case, case_url, title, image_url)
    VALUES (?, ?, ?, ?)
"""

for row in cases:
    case_id, case_name = row
    try:
        matches = scrape_tmz_search_results(case_id, case_name)
        for match in matches:
            cursor.execute(insert_sql, match["fk_case"], match["case_url"], match["title"], match["image_url"])
        conn.commit()
        logging.info(f"Inserted {len(matches)} links for case ID {case_id}")
    except Exception as e:
        logging.error(f"Error inserting links for case {case_id}: {e}")

cursor.close()
conn.close()
logging.info("Script completed successfully.")
