import pyodbc, requests, json

conn = pyodbc.connect('DSN=Docketwatch;TrustServerCertificate=yes;')
cursor = conn.cursor()
cursor.execute('SELECT gemini_api FROM docketwatch.dbo.utilities')
api_key = cursor.fetchone()[0]
cursor.close()
conn.close()

print(f"API Key: {api_key[:20]}...{api_key[-10:]}")

url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
payload = {'contents': [{'role': 'user', 'parts': [{'text': 'Hello'}]}]}
response = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))

print(f'Status: {response.status_code}')
print(f'Response: {response.text[:1000]}')
