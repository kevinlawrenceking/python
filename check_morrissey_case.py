import pyodbc

conn = pyodbc.connect('DSN=Docketwatch;TrustServerCertificate=yes;')
cursor = conn.cursor()
cursor.execute('SELECT case_name, case_number, case_url, pacer_id FROM docketwatch.dbo.cases WHERE id = 84389')
row = cursor.fetchone()
if row:
    print(f'Case: {row.case_name}')
    print(f'Number: {row.case_number}')
    print(f'PACER ID: {row.pacer_id}')
    print(f'URL: {row.case_url}')
else:
    print('Case not found')
cursor.close()
conn.close()
