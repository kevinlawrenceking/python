"""Test if parsing works on actual HTML from database"""
import pyodbc
from summary_parser import parse_ai_summary

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
conn.setencoding(encoding="utf-8")
cur = conn.cursor()

# Get the HTML we checked earlier
cur.execute("""
    SELECT summary_ai_html
    FROM documents 
    WHERE doc_uid = 'DCA15712-633F-423F-8D02-67451BE642FD'
""")

row = cur.fetchone()
if row and row.summary_ai_html:
    print("Parsing HTML from database...")
    parsed = parse_ai_summary(row.summary_ai_html)
    print(f"\nParsed event_summary: {repr(parsed['event_summary'])}")
    print(f"Parsed newsworthiness: {repr(parsed['newsworthiness'])}")
    print(f"Parsed key_details count: {len(parsed['key_details'])}")
    print(f"\nFull parsed dict:")
    for key, value in parsed.items():
        if key != 'key_details':
            print(f"  {key}: {repr(value[:100] if isinstance(value, str) and len(value) > 100 else value)}")
else:
    print("No HTML found")

conn.close()
