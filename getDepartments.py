import requests
import pyodbc
from datetime import datetime

# **Database Connection**
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = pyodbc.connect(DB_CONNECTION)
cursor = conn.cursor()

# **Ensure `departments` Table Exists**
create_table_query = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='departments' AND xtype='U')
CREATE TABLE docketwatch.dbo.departments (
    ID INT PRIMARY KEY,
    name NVARCHAR(100),
    fk_courthouse INT,
    created_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (fk_courthouse) REFERENCES docketwatch.dbo.courthouses(ID)
)
"""
cursor.execute(create_table_query)
conn.commit()

# **Fetch All Courthouse IDs**
cursor.execute("SELECT ID FROM docketwatch.dbo.courthouses")
courthouse_ids = [row[0] for row in cursor.fetchall()]

# **Loop Through Each Courthouse and Fetch Departments**
API_BASE_URL = "https://media.lacourt.org/lascmediaproxy/api/AzureApi/GetCriminalDepartments/"

for courthouse_id in courthouse_ids:
    print(f"\nFetching departments for Courthouse ID: {courthouse_id}")

    response = requests.get(f"{API_BASE_URL}{courthouse_id}")

    if response.status_code == 200:
        data = response.json()

        if data["isSuccess"]:
            departments = data["resultList"]

            for department in departments:
                dept_id = int(department["key"])
                dept_name = department["value"]

                # **Check if Department Already Exists**
                check_query = "SELECT COUNT(*) FROM docketwatch.dbo.departments WHERE ID = ?"
                cursor.execute(check_query, (dept_id,))
                count = cursor.fetchone()[0]

                if count == 0:
                    # **Insert New Department**
                    insert_query = """
                    INSERT INTO docketwatch.dbo.departments (ID, name, fk_courthouse, created_at)
                    VALUES (?, ?, ?, ?)
                    """
                    cursor.execute(insert_query, (dept_id, dept_name, courthouse_id, datetime.now()))
                    print(f"Inserted: {dept_name} (ID: {dept_id})")

            # **Commit Changes**
            conn.commit()
            print(f"✅ Departments updated for Courthouse {courthouse_id}")

        else:
            print(f"❌ API Error: {data['errorMessage']}")

    else:
        print(f"❌ API Request Failed! Status Code: {response.status_code}")

# **Close Connection**
cursor.close()
conn.close()
print("Script Completed Successfully!")
