#!/usr/bin/env python3
import pyodbc
import sys

def debug_case_alert(case_id):
    """Debug the case alert for a specific case ID."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print(f"🔍 Debugging case alert for case ID: {case_id}")
        print("=" * 60)
        
        # Check if case exists
        cursor.execute("SELECT id, case_number, case_name FROM docketwatch.dbo.cases WHERE id = ?", (case_id,))
        case = cursor.fetchone()
        
        if not case:
            print(f"❌ Case {case_id} not found")
            return False
        
        print(f"✅ Case found: {case.case_number} - {case.case_name}")
        
        # Check for unemailed events
        cursor.execute("""
            SELECT id, event_description, event_date, created_at, emailed
            FROM docketwatch.dbo.case_events
            WHERE fk_cases = ?
            ORDER BY created_at DESC
        """, (case_id,))
        
        events = cursor.fetchall()
        print(f"📄 Found {len(events)} total events")
        
        unemailed_events = [e for e in events if e.emailed == 0]
        print(f"📧 Found {len(unemailed_events)} unemailed events")
        
        if not unemailed_events:
            print("ℹ️  No unemailed events - script will exit normally")
            return True
        
        # Show unemailed events
        for event in unemailed_events[:3]:  # Show first 3
            print(f"   Event {event.id}: {event.event_description[:50]}...")
            
            # Check documents for this event
            cursor.execute("""
                SELECT doc_id, rel_path, pdf_title
                FROM docketwatch.dbo.documents
                WHERE fk_case_event = ?
            """, (event.id,))
            
            docs = cursor.fetchall()
            print(f"     Documents: {len(docs)}")
            
            for doc in docs:
                doc_id, rel_path, pdf_title = doc
                status = "✅ Has path" if rel_path and rel_path != "pending" else "⏳ Pending"
                print(f"       Doc {doc_id}: {pdf_title} - {status}")
        
        # Check celebrities
        cursor.execute("""
            SELECT celebrity_name
            FROM docketwatch.dbo.case_celebrities
            WHERE fk_cases = ?
        """, (case_id,))
        
        celebs = cursor.fetchall()
        print(f"🌟 Found {len(celebs)} celebrities")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    case_id = sys.argv[1] if len(sys.argv) > 1 else "107756"
    debug_case_alert(case_id)