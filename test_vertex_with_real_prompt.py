"""
Test to see what prompt is being sent and test Vertex AI directly
"""
import pyodbc

conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

event_id = "CDCA326E-16FF-4BD2-A6D1-26758D366DFD"

# Get event data
cursor.execute("""
    SELECT 
        d.doc_uid,
        d.event_summary,
        d.summary_ai,
        e.event_description,
        e.event_date,
        c.case_name,
        c.case_number
    FROM docketwatch.dbo.documents d
    JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
    JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
    WHERE e.id = CAST(? AS uniqueidentifier)
      AND d.event_summary IS NOT NULL
    ORDER BY d.date_downloaded ASC
""", (event_id,))

docs = cursor.fetchall()
print(f"Found {len(docs)} documents with summaries\n")

if docs:
    case_name = docs[0].case_name
    case_number = docs[0].case_number
    event_desc = docs[0].event_description
    event_date = docs[0].event_date.strftime('%Y-%m-%d') if hasattr(docs[0].event_date, 'strftime') else str(docs[0].event_date)
    
    document_summaries = []
    for idx, doc in enumerate(docs, 1):
        doc_summary = doc.event_summary or doc.summary_ai or "No summary available"
        if len(doc_summary) > 500:
            doc_summary = doc_summary[:500] + "..."
        document_summaries.append(f"Document {idx}: {doc_summary}")
    
    combined_docs = "\n\n".join(document_summaries)
    
    prompt = f"""You are a legal journalist. Create a brief event-level summary that synthesizes the following document summaries into a cohesive overview.

CASE INFORMATION:
Case: {case_name} ({case_number})
Event Date: {event_date}
Event Description: {event_desc}

DOCUMENT SUMMARIES:
{combined_docs}

Instructions:
- Write 2-4 sentences that capture the overall significance of this event
- Focus on what happened and why it matters
- If multiple documents describe the same event from different angles, synthesize them
- Do not list documents separately - create a unified narrative
- Keep it concise and journalist-friendly
- Do not use markdown or HTML formatting

Event Summary:"""

    print("Prompt length:", len(prompt), "characters")
    print("\n" + "="*70)
    print("Testing Vertex AI with this prompt...")
    print("="*70)
    
    from vertex_ai_helper import generate_content_vertex
    
    try:
        result = generate_content_vertex(prompt, temperature=0.5, max_tokens=500)
        print("\nSUCCESS!")
        print("\nGenerated summary:")
        print("-"*70)
        print(result)
        print("-"*70)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

cursor.close()
conn.close()
