import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pyodbc
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
WEBSITE_URL = "https://www.luigimangioneinfo.com/updates/"
DB_DSN = "DSN=Docketwatch;TrustServerCertificate=yes;"
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

# --- YOUR UPDATED EMAIL FUNCTION ---
def send_alert_email(subheading, content):
    """Sends an email notification for any detected change."""
    subject = "WebsiteWatch Alert: New Update on luigimangioneinfo.com"
    body = f"""
    <html><body>
        <h2>Website Update Alert</h2>
        <p>A new update has been posted to <a href="{WEBSITE_URL}">{WEBSITE_URL}</a></p>
        <p><strong>Section:</strong> {subheading}</p>
        <p><strong>Details:</strong></p>
        <blockquote style="border-left: 2px solid #ccc; padding-left: 10px; font-style: italic;">{content}</blockquote>
    </body></html>
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg.as_string())
        print(f"SUCCESS: Email alert sent for new content in '{subheading}'.")
    except Exception as e:
        print(f"ERROR: Failed to send email for '{subheading}': {e}")

def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = pyodbc.connect(DB_DSN)
        return conn
    except Exception as e:
        print(f"FATAL: Database connection failed: {e}")
        return None

def main():
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        print(f"Fetching content from {WEBSITE_URL}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        resp = requests.get(WEBSITE_URL, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"FATAL: Failed to fetch website content: {e}")
        conn.close()
        return

    soup = BeautifulSoup(resp.content, "html.parser")
    all_prose_divs = soup.find_all("div", class_="prose")

    if not all_prose_divs:
        print("WARNING: No content sections with class 'prose' were found.")
        conn.close()
        return

    ids_to_keep_active = []
    run_timestamp = datetime.now()

    for prose_div in all_prose_divs:
        header = prose_div.find("h3")
        if not header: continue
        subheading = header.get_text(strip=True)
        
        list_element = prose_div.find("ul")
        if not list_element: continue
            
        bullet_points = list_element.find_all("li")
        for point in bullet_points:
            bullet_text = point.get_text(" ", strip=True)

            cursor.execute(
                "SELECT Id FROM MonitoredContent WHERE Subheading = ? AND BulletText = ? AND IsActive = 1",
                (subheading, bullet_text)
            )
            result = cursor.fetchone()

            if result:
                item_id = result.Id
                ids_to_keep_active.append(item_id)
                cursor.execute("UPDATE MonitoredContent SET LastSeen = ? WHERE Id = ?", (run_timestamp, item_id))

            else:
                print(f"CHANGE DETECTED in '{subheading}': Found new content.")
                cursor.execute(
                    """
                    INSERT INTO MonitoredContent (Subheading, BulletText, FirstSeen, LastSeen, IsActive)
                    VALUES (?, ?, ?, ?, 1);
                    """,
                    (subheading, bullet_text, run_timestamp, run_timestamp)
                )
                newly_inserted_id = cursor.execute("SELECT @@IDENTITY;").fetchval()
                if newly_inserted_id:
                    ids_to_keep_active.append(newly_inserted_id)
                
                # --- THIS IS THE CORRECTED FUNCTION CALL ---
                send_alert_email(subheading, bullet_text)

    if not ids_to_keep_active:
        cursor.execute("UPDATE MonitoredContent SET IsActive = 0 WHERE IsActive = 1")
        print("INFO: Page appears to be blank. Deactivating all items.")
    else:
        placeholders = ','.join(['?'] * len(ids_to_keep_active))
        deactivation_query = f"UPDATE MonitoredContent SET IsActive = 0 WHERE IsActive = 1 AND Id NOT IN ({placeholders})"
        cursor.execute(deactivation_query, ids_to_keep_active)
        if cursor.rowcount > 0:
            print(f"INFO: Deactivated {cursor.rowcount} bullet point(s) that were removed or changed.")

    conn.commit()
    print("\nProcess finished. Database has been updated successfully.")
    conn.close()

if __name__ == "__main__":
    main()