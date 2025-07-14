import requests
import pyodbc
from datetime import datetime, timedelta
from case_processing import process_case  # Case processing functions
from celebrity_matches import check_celebrity_matches  # Celebrity match processing

# **Database Connection**
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
try:
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
except Exception as e:
    print("❌ Error connecting to database:", e)
    exit(1)

# **API Parameters**
COURT_ID = "150650"  # Example: Inglewood Courthouse
DEPARTMENT_ID = "108124"  # Example: Inglewood Dept.
DATE_FROM = datetime.strptime("03-07-2025", "%m-%d-%Y")
DATE_TO = datetime.strptime("03-09-2025", "%m-%d-%Y")

# **Function to Check if Date Exists in Log**
def is_already_imported(court_id, department_id, hearing_date):
    cursor.execute("""
        SELECT COUNT(*) FROM docketwatch.dbo.hearingImportLog
        WHERE court_id = ? AND department_id = ? AND date_imported = ?
    """, (court_id, department_id, hearing_date))
    
    return cursor.fetchone()[0] > 0

# **Loop Over Each Date in Range**
current_date = DATE_FROM
while current_date <= DATE_TO:
    date_str = current_date.strftime("%m-%d-%Y")

    # **Check if Already Imported**
    if is_already_imported(COURT_ID, DEPARTMENT_ID, current_date):
        print(f"⏭️ Skipping {date_str} - Already Imported")
        current_date += timedelta(days=1)
        continue  # Move to next date

    API_URL = f"https://media.lacourt.org/lascmediaproxy/api/AzureApi/CriminalCalendarSearchByLocationNew/CR/{COURT_ID}/{DEPARTMENT_ID}/{date_str}/{date_str}"
    print(f"📡 Sending request to API: {API_URL}")

    response = requests.get(API_URL)

    if response.status_code == 200:
        data = response.json()

        if data["isSuccess"]:
            hearings = data["resultList"]
            print(f"📋 Number of hearings received: {len(hearings)}")

            for idx, hearing in enumerate(hearings):
                print(f"⚖️ Processing hearing {idx + 1} of {len(hearings)}")

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
                
                try:
                    cms_location_id = int(hearing["cmsLocationID"])
                except Exception as e:
                    print(f"⚠️ Error converting cms_location_id: {e}")
                    continue

                department_name = hearing["department"]

                # **Find fk_court and county_code from `courts`**
                cursor.execute("""
                    SELECT ct.court_code, co.code as county_code FROM docketwatch.dbo.courts ct 
                    INNER JOIN [dbo].[counties] co on co.id = ct.fk_county 
                    WHERE ct.court_id = ? 
                """, (cms_location_id,))
                court_result = cursor.fetchone()
                fk_court = court_result[0] if court_result else "UNK"
                county_code = court_result[1] if court_result else "UNK"

                # **Find fk_case from `cases`**
                cursor.execute("SELECT ID FROM docketwatch.dbo.cases WHERE case_number = ?", (case_number,))
                case_result = cursor.fetchone()
                fk_case = case_result[0] if case_result else None

                # **Insert Case if it Doesn't Exist**
                if fk_case is None:
                    insert_case_query = """
                    INSERT INTO docketwatch.dbo.cases (case_number, case_name, case_type, case_status, fk_court, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?, GETDATE(), GETDATE())
                    """
                    cursor.execute(insert_case_query, (case_number, case_name, case_type, case_status, fk_court))
                    conn.commit()
                    
                    cursor.execute("SELECT ID FROM docketwatch.dbo.cases WHERE case_number = ?", (case_number,))
                    new_case_result = cursor.fetchone()
                    fk_case = new_case_result[0] if new_case_result else None

                    # **Process Case Name & Parties**
                    process_case(fk_case, case_number, case_name, fk_court, county_code)

                # **Find fk_courthouse from `courts`**
                cursor.execute("SELECT court_id FROM docketwatch.dbo.courts WHERE court_id = ?", (cms_location_id,))
                court_result = cursor.fetchone()
                fk_courthouse = court_result[0] if court_result else None

                # **Find fk_departments from `departments`**
                cursor.execute("SELECT ID FROM docketwatch.dbo.departments WHERE name = ?", (department_name,))
                dept_result = cursor.fetchone()
                fk_departments = dept_result[0] if dept_result else None

                # **Check if Hearing Already Exists**
                check_query = """
                SELECT COUNT(*) FROM docketwatch.dbo.hearings
                WHERE fk_case = ? AND hearing_datetime = ? AND hearing_type = ?
                """
                cursor.execute(check_query, (fk_case, hearing_datetime, hearing_type))
                count = cursor.fetchone()[0]

                if count == 0:
                    # **Insert New Hearing**
                    insert_query = """
                    INSERT INTO docketwatch.dbo.hearings (
                        fk_case, fk_departments, fk_courthouse, hearing_type, hearing_datetime,
                        court_session_id, court_session_description, calendar_number,
                        case_utype_id, case_utype_description, memo, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    cursor.execute(insert_query, (
                        fk_case, fk_departments, fk_courthouse, hearing_type, hearing_datetime,
                        court_session_id, court_session_description, calendar_number,
                        case_utype_id, case_utype_description, memo, datetime.now()
                    ))
                    print(f"✅ Inserted hearing: {hearing_type} on {hearing_datetime} (fk_court: {fk_court})")

            # **Log the Import Date**
            cursor.execute("""
                INSERT INTO docketwatch.dbo.hearingImportLog (court_id, department_id, date_imported, timestamp)
                VALUES (?, ?, ?, GETDATE())
            """, (COURT_ID, DEPARTMENT_ID, current_date))
            print(f"📝 Logged Import: Court {COURT_ID}, Dept {DEPARTMENT_ID}, Date {date_str}")

            conn.commit()

        else:
            print(f"❌ API Response Error for {date_str}: {data['errorMessage']}")

    else:
        print(f"❌ API Request Failed for {date_str}! Status Code: {response.status_code}")

    # **Move to Next Date**
    current_date += timedelta(days=1)

# **Run Celebrity Match Check After All Hearings Are Processed**
check_celebrity_matches()

# **Close Connection**
cursor.close()
conn.close()
print("🎯 Script Completed Successfully!")
