import json
import pyodbc

# Load JSON
with open(r"\\10.146.176.84\general\docketwatch\python\followed_cases_m.json", "r", encoding="utf-8") as f:
    data = json.load(f)

cases = data.get("resultList", [])

# DB Connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# Insert Cases
for case in cases:
    cursor.execute("""
        INSERT INTO dbo.followed_cases (
            email_address, cell_phone, case_number, bar_number, map_id, 
            application_id, case_title, user_id, date_added, last_notified, 
            data_source, status, unique_id, retry_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case.get("emailAddress"),
        case.get("cellPhone"),
        case.get("caseNumber"),
        case.get("barNumber"),
        case.get("caseID"),
        case.get("applicationID"),
        case.get("caseTitle"),
        case.get("userID"),
        case.get("dateAdded"),
        case.get("lastNotified"),
        case.get("dataSource"),
        case.get("status"),
        case.get("uniqueID"),
        case.get("retryCount"),
    ))

conn.commit()
cursor.close()
conn.close()

print("Insert complete.")
