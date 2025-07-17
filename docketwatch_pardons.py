import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import pyodbc
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BASE_URL = "https://www.justice.gov"
PARDONS_URL = f"{BASE_URL}/pardon/clemency-grants-president-donald-j-trump-2025-present"

# Email config
FROM_EMAIL = "it@tmz.com"
SMTP_SERVER = "mx0a-00195501.pphosted.com"
SMTP_PORT = 25
TO_EMAILS = [
    "Jennifer.Delgado@tmz.com",
    "Kevin.King@tmz.com",
    "marlee.chartash@tmz.com",
    "Priscilla.Hwang@tmz.com",
    "Shirley.Troche@tmz.com"
]

def send_pardon_email(name, district, sentenced, offense, pardon_date, link):
    subject = f"DocketWatch Alert: New Presidential Pardon – {name}"
    body = f"""..."""  # Your HTML content

    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)  # Header shows all recipients
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            # *** The third argument must be a LIST of emails, not a string ***
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        print(f"ALERT: Email sent for new pardon {name}")
    except Exception as e:
        print(f"ERROR: Failed to send email for {name}: {e}")


def main():
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
    except Exception as e:
        print(f"ERROR: Could not connect to DB: {e}")
        return

    try:
        resp = requests.get(PARDONS_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to fetch pardons page: {e}")
        return

    soup = BeautifulSoup(resp.content, "html.parser")
    h3_list = soup.find_all("h3")

    inserted = 0
    skipped = 0
    total_rows = 0

    for h3 in h3_list:
        h3_text = h3.get_text(strip=True)
        if " - " in h3_text:
            date_str = h3_text.split(" - ")[0].strip()
        else:
            date_str = h3_text.strip()
        try:
            pardon_date = datetime.strptime(date_str, "%B %d, %Y").date()
        except Exception as ex:
            print(f"WARNING: Skipping h3 with bad date format: {h3_text}")
            continue

        table = h3.find_next_sibling("table")
        if not table:
            print(f"WARNING: No table found after header: {h3_text}")
            continue

        rows = table.find_all("tr")
        for i, row in enumerate(rows, 1):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            name = cells[0].get_text(strip=True)
            district = cells[1].get_text(strip=True)
            sentenced = cells[2].get_text(strip=True)
            offense = cells[3].get_text(strip=True)
            link_tag = cells[0].find("a")
            link = urljoin(BASE_URL, link_tag["href"]) if link_tag else None

            # Deduplication check: must check by BOTH name and pardon_date
            cursor.execute(
                "SELECT COUNT(*) FROM docketwatch.dbo.pardons WHERE name = ?",
                (name)
            )
            already_exists = cursor.fetchone()[0]
            if already_exists:
                skipped += 1
                continue

            # Insert
            try:
                cursor.execute(
                    """
                    INSERT INTO docketwatch.dbo.pardons
                        ([name],[district],[sentenced],[offense],[pardon_date],[link],[timestamp])
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, district, sentenced, offense, pardon_date, link, datetime.now())
                )
                inserted += 1
                print(f"Inserted: {name} / {pardon_date}")

                # Send email alert
                send_pardon_email(name, district, sentenced, offense, pardon_date, link)

            except Exception as ex:
                print(f"ERROR: DB insert failed for {name} ({pardon_date}): {ex}")

            total_rows += 1

    try:
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"ERROR: Final DB commit/close error: {e}")

    print(f"\nDone! Inserted: {inserted}, Skipped (already in DB): {skipped}")

if __name__ == "__main__":
    main()
