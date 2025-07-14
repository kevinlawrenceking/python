
import os
import pyodbc
from case_processing import process_case
from celebrity_matches import check_celebrity_matches

# === DB CONNECTION ===
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# === Fetch Unprocessed Cases ===
cursor.execute("""
    SELECT TOP 1000  
        c.[id] as case_id,
        c.[case_number],
        c.[case_name],
        c.[fk_court] as court_code,
        cn.code as county_code
    FROM [docketwatch].[dbo].[cases] c
    INNER JOIN docketwatch.[dbo].[courts] o ON c.fk_court = o.court_code
     inner join [docketwatch].[dbo].[counties] cn on o.fk_county = cn.id
    WHERE c.case_parties_checked = 0 
      AND c.id NOT IN (
          SELECT fk_case FROM docketwatch.[dbo].[case_parties]
      )
    ORDER BY c.id DESC
""")
cases = cursor.fetchall()

# === Process Each Case ===
for row in cases:
    case_id, case_number, case_name, court_code, county_code = row
    print(f"Processing case {case_id}: {case_name} ({case_number}) in {court_code}")

    try:
        process_case(case_id, case_number, case_name, court_code, county_code)
        check_celebrity_matches()
        
        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET case_parties_checked = 1
            WHERE id = ?
        """, (case_id,))
        conn.commit()
        print(f"Updated case {case_id} as processed.")
    except Exception as e:
        print(f"Error processing case {case_id}: {e}")

cursor.close()
conn.close()
