"""
Test event summary generation with fresh imports
"""
import sys
import pyodbc
import google.generativeai as genai

# Get database connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# Get API key
cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
api_key = cursor.fetchone()[0]
print(f"API Key loaded: {api_key[:15]}...{api_key[-5:]}")

# Configure Gemini
genai.configure(api_key=api_key)

# Use the Flash model (free tier)
model_name = "gemini-2.5-flash"
print(f"Using model: {model_name}")

# Get event data
event_id = "CDCA326E-16FF-4BD2-A6D1-26758D366DFD"

cursor.execute("""
    SELECT 
        d.doc_uid,
        d.event_summary,
        d.summary_ai,
        d.newsworthiness,
        d.newsworthiness_reason,
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
print(f"\nFound {len(docs)} documents with summaries")

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

    print("\n" + "="*70)
    print("GENERATING EVENT SUMMARY")
    print("="*70)
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.5,
                max_output_tokens=300
            ),
            safety_settings={
                'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
            }
        )
        
        # Handle response
        if response.candidates and response.candidates[0].content.parts:
            event_summary = response.candidates[0].content.parts[0].text.strip()
        else:
            print(f"Response blocked. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'}")
            print(f"Safety ratings: {response.candidates[0].safety_ratings if response.candidates else 'N/A'}")
            raise ValueError("Content was blocked by safety filters")
        
        print("\n✓ SUCCESS!")
        print("\nGenerated Event Summary:")
        print("-"*70)
        print(event_summary)
        print("-"*70)
        
        # Update database
        cursor.execute("""
            UPDATE docketwatch.dbo.case_events
            SET summarize = ?
            WHERE id = CAST(? AS uniqueidentifier)
        """, (event_summary, event_id))
        
        conn.commit()
        print("\n✓ Database updated")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

cursor.close()
conn.close()
