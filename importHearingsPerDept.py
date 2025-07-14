import requests
import pyodbc
from datetime import datetime, timedelta
from case_processing import process_case  # Process parties & names
from celebrity_matches import check_celebrity_matches  # Check celebrity matches

# **Database Connection**
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = pyodbc.connect(DB_CONNECTION)
cursor = conn.cursor()

# **Find the next 10 departments to process (excluding already processed ones)**
query = """
SELECT TOP 10 c.court_id, c.court_code, d.id as department_id  
FROM [dbo].[courts] c 
INNER JOIN [dbo].[departments] d ON d.fk_court_id = c.court_id
WHERE NOT EXISTS (
    SELECT 1 FROM docketwatch.dbo.hearingImportLog h 
    WHERE h.court_id = c.court_id 
    AND h.department_id = d.id
)
ORDER BY d.id;
"""
cursor.execute(query)
departments = cursor.fetchall()

if not departments:
    print("✅ All departments have been processed. No new imports needed.")
    cursor.close()
    conn.close()
    exit()

DATE_FROM = datetime.today().strftime("%m-%d-%Y")
DATE_TO = (datetime.today() + timedelta(days=60)).strftime("%m-%d-%Y")

for COURT_ID, COURT_CODE, DEPARTMENT_ID in departments:
    API_URL = f"https://media.lacourt.org/lascmediaproxy/api/AzureApi/CriminalCalendarSearchByLocationNew/CR/{COURT_ID}/{DEPARTMENT_ID}/{DATE_FROM}/{DATE_TO}"

    print(f"Processing hearings for Court ID: {COURT_ID}, Department ID: {DEPARTMENT_ID}")
    print(f"Fetching data from: {API_URL}")

    response = requests.get(API_URL)

    if response.status_code == 200:
        data = response.json()

        if data["isSuccess"]:
            hearings = data["resultList"]
            print(f"✅ Received {len(hearings)} hearings for Dept {DEPARTMENT_ID}.")

            for hearing in hearings:
                # **Extract Hearing Data**
                case_number = hearing["caseNumber"][:50]
                case_name = " ".join(hearing["caseTitle"].splitlines())[:255]
                case_type = hearing["caseType"][:400]
                case_status = hearing.get("caseStatus", "Unknown")[:100]
                hearing_type = hearing["hearingType"]
                hearing_datetime = hearing["hearingDateTime"]
                court_session_id = hearing["courtSessionID"]
                court_session_description = hearing["courtSessionDescription"]
                calendar_number = hearing["calendarNumber"]
                case_utype_id = hearing["caseUTypeID"]
                case_utype_description = hearing["caseUTypeDescription"]
                memo = hearing["memo"]
                cms_location_id = int(hearing["cmsLocationID"])  # This links to courts.court_id
                department_name = hearing["department"]

                # **Find fk_court_id from `courts` (Numerical ID)**
                cursor.execute("SELECT court_code FROM docketwatch.dbo.courts WHERE court_id = ?", (cms_location_id,))
                court_result = cursor.fetchone()
                fk_court = court_result[0] if court_result else None  # VARCHAR court_code

                # **Check if Case Exists**
                cursor.execute("SELECT ID FROM docketwatch.dbo.cases WHERE case_number = ?", (case_number,))
                case_result = cursor.fetchone()
                fk_case = case_result[0] if case_result else None

                if fk_case is None:
                    # **Insert Case**
                    insert_case_query = """
                    INSERT INTO docketwatch.dbo.cases (case_number, case_name, case_type, case_status, fk_court, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?, GETDATE(), GETDATE())
                    """
                    cursor.execute(insert_case_query, (case_number, case_name, case_type, case_status, fk_court))
                    conn.commit()

                    # **Retrieve the Inserted Case ID**
                    cursor.execute("SELECT ID FROM docketwatch.dbo.cases WHERE case_number = ?", (case_number,))
                    fk_case = cursor.fetchone()[0]

                    # **Process Case Name & Parties**
                    process_case(fk_case, case_number, case_name, fk_court, "LAC")  # Assuming "LAC" is county_code

                # **Find fk_department from `departments`**
                cursor.execute("SELECT ID FROM docketwatch.dbo.departments WHERE name = ?", (department_name,))
                dept_result = cursor.fetchone()
                fk_department = dept_result[0] if dept_result else None

                if fk_department is None:
                    print(f"⚠️ Department '{department_name}' not found for court {cms_location_id}. Will insert hearing without dept.")

                # **Check if Hearing Exists**
                check_query = """
                SELECT COUNT(*) 
                FROM docketwatch.dbo.hearings h
                INNER JOIN docketwatch.dbo.cases c ON c.id = h.fk_case
                WHERE c.case_number = ? AND h.hearing_datetime = ?
                """
                cursor.execute(check_query, (case_number, hearing_datetime))
                count = cursor.fetchone()[0]

                if count == 0:
                    # **Insert New Hearing**
                    insert_query = """
                    INSERT INTO docketwatch.dbo.hearings (
                        fk_case, fk_department, fk_court_id, hearing_type, hearing_datetime,
                        court_session_id, court_session_description, calendar_number,
                        case_utype_id, case_utype_description, memo, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    cursor.execute(insert_query, (
                        fk_case, fk_department, COURT_ID, hearing_type, hearing_datetime,
                        court_session_id, court_session_description, calendar_number,
                        case_utype_id, case_utype_description, memo, datetime.now()
                    ))
                    print(f"✅ Inserted hearing: {hearing_type} on {hearing_datetime} (fk_court_id: {COURT_ID})")

            # **Commit Changes**
            conn.commit()
            print(f"✅ Hearings for Department {DEPARTMENT_ID} updated successfully!")

            # **Log the Import**
            for single_date in [DATE_FROM, DATE_TO]:
                cursor.execute("""
                INSERT INTO docketwatch.dbo.hearingImportLog (court_id, department_id, date_imported, timestamp)
                VALUES (?, ?, ?, GETDATE())
                """, (COURT_ID, DEPARTMENT_ID, single_date))
            
            conn.commit()
            print(f"✅ Logged hearing import for Dept {DEPARTMENT_ID}.")

        else:
            print(f"❌ API Response Error: {data['errorMessage']}")

    else:
        print(f"❌ API Request Failed! Status Code: {response.status_code}")

# **Check for Celebrity Matches**
check_celebrity_matches()
print("✅ Checked for celebrity matches.")

# **Close Connection**
cursor.close()
conn.close()
print("🎯 Script Completed Successfully!")
