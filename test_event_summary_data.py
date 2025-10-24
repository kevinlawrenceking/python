"""
Test Event Summary Generation (No API)

Tests the event summary generation logic without calling Gemini API.
Shows what data would be sent to Gemini for summary generation.
"""

import sys
import os
import pyodbc

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_event_data(event_id):
    """Show what data would be used to generate an event summary."""
    
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    print(f"Testing event: {event_id}\n")
    print("="*70)
    
    # Get all documents for this event
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.event_summary,
            d.summary_ai,
            d.newsworthiness,
            d.newsworthiness_reason,
            e.event_description,
            e.event_date,
            e.summarize as existing_event_summary,
            c.case_name,
            c.case_number
        FROM docketwatch.dbo.documents d
        JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
        JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
        WHERE e.id = CAST(? AS uniqueidentifier)
        ORDER BY d.date_downloaded ASC
    """, (event_id,))
    
    docs = cursor.fetchall()
    
    if not docs:
        print("❌ No documents found for this event")
        return
    
    print(f"CASE: {docs[0].case_name} ({docs[0].case_number})")
    print(f"EVENT: {docs[0].event_description}")
    print(f"DATE: {docs[0].event_date}")
    print(f"EXISTING EVENT SUMMARY: {docs[0].existing_event_summary or '(None)'}")
    print()
    print(f"Found {len(docs)} document(s) with summaries:\n")
    
    for idx, doc in enumerate(docs, 1):
        print(f"{'='*70}")
        print(f"DOCUMENT {idx}")
        print(f"{'='*70}")
        print(f"DOC_UID: {doc.doc_uid}")
        print(f"Newsworthy: {doc.newsworthiness}")
        if doc.newsworthiness_reason:
            print(f"Reason: {doc.newsworthiness_reason[:200]}...")
        print()
        
        if doc.event_summary:
            print(f"EVENT SUMMARY (from doc):")
            print(f"{doc.event_summary}")
            print()
        
        if doc.summary_ai:
            print(f"AI SUMMARY (first 300 chars):")
            print(f"{doc.summary_ai[:300]}...")
            print()
    
    print(f"{'='*70}")
    print("\nPROMPT THAT WOULD BE SENT TO GEMINI:")
    print(f"{'='*70}\n")
    
    # Build the prompt that would be sent
    document_summaries = []
    for idx, doc in enumerate(docs, 1):
        doc_summary = doc.event_summary or doc.summary_ai or "No summary available"
        if len(doc_summary) > 500:
            doc_summary = doc_summary[:500] + "..."
        document_summaries.append(f"Document {idx}: {doc_summary}")
    
    combined_docs = "\n\n".join(document_summaries)
    
    prompt = f"""You are a legal journalist. Create a brief event-level summary that synthesizes the following document summaries into a cohesive overview.

CASE INFORMATION:
Case: {docs[0].case_name} ({docs[0].case_number})
Event Date: {docs[0].event_date}
Event Description: {docs[0].event_description}

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
    
    print(prompt)
    print(f"\n{'='*70}")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_event_summary_data.py <event_id>")
        sys.exit(1)
    
    test_event_data(sys.argv[1])
