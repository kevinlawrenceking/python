"""
Simple test to debug generate_event_summary
"""
import pyodbc
import traceback
from summarize_document_event import generate_event_summary

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

event_id = "CDCA326E-16FF-4BD2-A6D1-26758D366DFD"

print(f"Testing event: {event_id}")
print()

try:
    result = generate_event_summary(cursor, event_id)
    if result:
        print("SUCCESS! Generated summary:")
        print(result)
    else:
        print("FAILED: Returned None")
except Exception as e:
    print(f"EXCEPTION: {e}")
    traceback.print_exc()

cursor.close()
conn.close()
