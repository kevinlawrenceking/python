"""Debug why parsing is failing"""
import pyodbc
from bs4 import BeautifulSoup

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
conn.setencoding(encoding="utf-8")
cur = conn.cursor()

cur.execute("""
    SELECT summary_ai_html
    FROM documents 
    WHERE doc_uid = 'DCA15712-633F-423F-8D02-67451BE642FD'
""")

row = cur.fetchone()
if row and row.summary_ai_html:
    soup = BeautifulSoup(row.summary_ai_html, 'html.parser')
    
    print("Looking for <h3> tags...")
    all_h3 = soup.find_all('h3')
    print(f"Found {len(all_h3)} h3 tags:")
    for h3 in all_h3:
        print(f"  Text: {repr(h3.get_text())}")
        print(f"  String: {repr(h3.string)}")
        print(f"  Stripped: {repr(h3.get_text().strip())}")
        print()
    
    print("\nTrying to find EVENT SUMMARY section...")
    event_section = soup.find('h3', string='EVENT SUMMARY')
    print(f"Direct string match: {event_section}")
    
    # Try with stripped text
    for h3 in soup.find_all('h3'):
        if h3.get_text().strip() == 'EVENT SUMMARY':
            print(f"Found with stripped text!")
            next_p = h3.find_next_sibling('p')
            if next_p:
                print(f"Next <p>: {next_p.get_text().strip()[:100]}")

conn.close()
