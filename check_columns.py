import pyodbc

conn = pyodbc.connect('DSN=Docketwatch;TrustServerCertificate=yes;')
cursor = conn.cursor()

print("\nStory columns in documents table:")
cursor.execute("""
    SELECT COLUMN_NAME 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'documents' 
    AND COLUMN_NAME LIKE 'story%' 
    ORDER BY COLUMN_NAME
""")
for row in cursor.fetchall():
    print(f"  - {row.COLUMN_NAME}")

print("\nStory columns in articles table:")
cursor.execute("""
    SELECT COLUMN_NAME 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'articles' 
    AND COLUMN_NAME LIKE 'story%' 
    ORDER BY COLUMN_NAME
""")
for row in cursor.fetchall():
    print(f"  - {row.COLUMN_NAME}")

cursor.close()
conn.close()
