import pyodbc

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    # Check the Morrissey case details
    cursor.execute("SELECT id, case_name, pacer_id FROM docketwatch.dbo.cases WHERE id = 84389")
    row = cursor.fetchone()
    if row:
        print(f"Case ID: {row[0]}")
        print(f"Name: {row[1]}")
        print(f"PACER ID: {row[2]}")
    else:
        print("Case 84389 not found")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
