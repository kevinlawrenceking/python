import pyodbc
import json
import sys

doc_uid = sys.argv[1] if len(sys.argv) > 1 else "C7EEE470-FB40-493B-A75C-ADCBD2BFAA8E"

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cur = conn.cursor()
cur.execute(
    """
    SELECT summary_ai_verifier_result, summary_ai_extraction_json, 
           LEFT(summary_ai, 200) as summary_preview
    FROM docketwatch.dbo.documents 
    WHERE doc_uid = CAST(? AS uniqueidentifier)
    """,
    doc_uid
)
row = cur.fetchone()

if not row:
    print(f"Document {doc_uid} not found")
    sys.exit(1)

print(f"=== Summary Verification for {doc_uid} ===\n")
print(f"Verifier Result: {row[0]}")
print(f"\nSummary Preview: {row[2]}...\n")

if row[1]:
    ext = json.loads(row[1])
    print(f"Extraction Data:")
    print(f"  - Adjudication Mode: {ext.get('adjudication_mode')}")
    print(f"  - Counts Convicted: {ext.get('counts_convicted')}")
    print(f"  - Counts Dismissed: {ext.get('counts_dismissed')}")
    print(f"  - Counts Alleged: {ext.get('counts_alleged')}")
    print(f"  - Confidence: {ext.get('confidence')}")
    print(f"  - Doc Type: {ext.get('doc_type')}")
    print(f"  - Filing Action Summary: {ext.get('filing_action_summary')[:150]}...")
else:
    print("No extraction JSON found")

conn.close()
