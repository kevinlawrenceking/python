"""
Check what case URLs are stored for tracked PACER cases
"""
import pyodbc

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("""
    SELECT TOP 5 id, case_name, case_number, case_url, pacer_id
    FROM docketwatch.dbo.cases 
    WHERE fk_tool = 2 AND status = 'Tracked' AND case_url IS NOT NULL
    ORDER BY id DESC
""")

print("Sample tracked PACER cases:")
for row in cursor.fetchall():
    print(f"Case ID: {row.id}")
    print(f"Name: {row.case_name}")
    print(f"Number: {row.case_number}")
    print(f"PACER ID: {row.pacer_id}")
    print(f"URL: {row.case_url}")
    print("---")

cursor.close()
conn.close()
