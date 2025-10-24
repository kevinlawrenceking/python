"""
Test event summary generation with detailed error output
"""
import pyodbc
from summarize_document_event import generate_event_summary
import traceback

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

event_id = "CDCA326E-16FF-4BD2-A6D1-26758D366DFD"

print("Testing event summary generation...")
print(f"Event ID: {event_id}")
print()

try:
    result = generate_event_summary(cursor, event_id)
    if result:
        print("✓ SUCCESS!")
        print(f"Summary: {result}")
    else:
        print("❌ Returned None")
except Exception as e:
    print(f"❌ ERROR: {e}")
    print()
    print("Full traceback:")
    traceback.print_exc()

cursor.close()
conn.close()
