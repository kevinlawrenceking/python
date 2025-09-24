#!/usr/bin/env python3
import pyodbc

def debug_event_query(case_id):
    """Debug the event query to see what's happening."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print(f"🔍 Debugging event query for case {case_id}")
        print("=" * 50)
        
        # Check events with emailed status
        cursor.execute("""
            SELECT id, event_description, emailed, created_at
            FROM docketwatch.dbo.case_events
            WHERE fk_cases = ?
            ORDER BY created_at DESC
        """, (case_id,))
        
        events = cursor.fetchall()
        print(f"📄 Found {len(events)} total events:")
        
        for event in events[:5]:  # Show first 5
            emailed_status = "✅ Emailed" if event.emailed == 1 else "📧 Not emailed"
            print(f"   Event {event.id}: {emailed_status}")
            print(f"      Description: {event.event_description[:50]}...")
            print()
        
        # Check just unemailed events
        cursor.execute("""
            SELECT id, event_description, emailed
            FROM docketwatch.dbo.case_events
            WHERE fk_cases = ? AND emailed = 0
        """, (case_id,))
        
        unemailed = cursor.fetchall()
        print(f"📧 Found {len(unemailed)} unemailed events")
        
        if unemailed:
            for event in unemailed:
                print(f"   Unemailed Event {event.id}: {event.event_description[:50]}...")
                
                # Check documents for this event
                cursor.execute("""
                    SELECT doc_id, rel_path, pdf_title
                    FROM docketwatch.dbo.documents
                    WHERE fk_case_event = ?
                """, (event.id,))
                
                docs = cursor.fetchall()
                print(f"      Has {len(docs)} documents")
                for doc in docs:
                    print(f"         Doc {doc.doc_id}: {doc.pdf_title}")
        
        # Try the exact query from the script
        cursor.execute("""
            SELECT e.id AS event_id, e.event_description, e.event_date, e.created_at, d.doc_uid, d.fk_case_event, d.rel_path, d.pdf_title, d.summary_ai_html, d.doc_id
            FROM docketwatch.dbo.case_events e
            LEFT JOIN docketwatch.dbo.documents d ON e.id = d.fk_case_event
            WHERE e.fk_cases = ? AND e.emailed = 0
            ORDER BY e.created_at DESC
        """, (case_id,))
        
        script_results = cursor.fetchall()
        print(f"🔧 Script's exact query returns: {len(script_results)} rows")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_event_query(107756)