import requests
import pyodbc
from datetime import datetime

# **API Endpoint**
API_URL = "https://media.lacourt.org/lascmediaproxy/api/AzureApi/GetCriminalCourthouses/"

# ** Connect to Database **
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# **Ensure `courthouses` Table Exists**
create_table_query = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='courthouses' AND xtype='U')
CREATE TABLE docketwatch.dbo.courthouses (
    ID INT PRIMARY KEY,
    name NVARCHAR(100),
    created_at DATETIME DEFAULT GETDATE()
)
"""
cursor.execute(create_table_query)
conn.commit()

# **Fetch API Data**
response = requests.get(API_URL)

if response.status_code == 200:
    data = response.json()

    if data["isSuccess"]:
        courthouses = data["resultList"]

        for courthouse in courthouses:
            courthouse_id = int(courthouse["key"])
            courthouse_name = courthouse["value"]

            # **Check if courthouse already exists**
            check_query = "SELECT COUNT(*) FROM docketwatch.dbo.courthouses WHERE ID = ?"
            cursor.execute(check_query, (courthouse_id,))
            count = cursor.fetchone()[0]

            if count == 0:
                # **Insert New Courthouse**
                insert_query = """
                INSERT INTO docketwatch.dbo.courthouses (ID, name, created_at)
                VALUES (?, ?, ?)
                """
                cursor.execute(insert_query, (courthouse_id, courthouse_name, datetime.now()))
                print(f"Inserted: {courthouse_name} ({courthouse_id})")

        # **Commit All Changes**
        conn.commit()
        print("✅ Courthouse data updated successfully!")

    else:
        print("❌ API Response Error:", data["errorMessage"])

else:
    print(f"❌ API Request Failed! Status Code: {response.status_code}")

# **Close Connection**
cursor.close()
conn.close()
