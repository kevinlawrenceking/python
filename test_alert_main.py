#!/usr/bin/env python3
"""
Simple test of the main alert functionality
"""
import sys
import os
import pyodbc
import logging
from datetime import datetime

# Add the same imports as the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from error_handler import create_error_notifier
except ImportError:
    # Create a simple mock if error_handler not available
    class MockErrorNotifier:
        def log_error(self, *args, **kwargs): pass
    def create_error_notifier(name): return MockErrorNotifier()

def test_main_alert(case_id):
    """Test the main alert functionality with debug output."""
    
    print(f"🧪 Testing alert for case {case_id}")
    print("=" * 50)
    
    # Setup basic logging
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger()
    
    # Initialize error notification system
    script_filename = "test_alert"
    error_notifier = create_error_notifier(script_filename)
    
    try:
        # Connect to database  
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("✅ Database connection established")
        
        # Get case info
        cursor.execute("SELECT id, case_number, case_name FROM docketwatch.dbo.cases WHERE id = ?", (case_id,))
        case = cursor.fetchone()
        
        if not case:
            print(f"❌ Case {case_id} not found")
            return False
        
        case_number = case.case_number
        case_name = case.case_name
        print(f"✅ Case: {case_number} - {case_name}")
        
        # Get events (same query as main script)
        cursor.execute("""
            SELECT e.id AS event_id, e.event_description, e.event_date, e.created_at, d.doc_uid, d.fk_case_event, d.rel_path, d.pdf_title, d.summary_ai_html, d.doc_id
            FROM docketwatch.dbo.case_events e
            LEFT JOIN docketwatch.dbo.documents d ON e.id = d.fk_case_event
            WHERE e.fk_cases = ? AND e.emailed = 0
            ORDER BY e.created_at DESC
        """, (case_id,))
        
        events = {}
        for row in cursor.fetchall():
            eid = row.event_id
            if eid not in events:
                events[eid] = {
                    "event_description": row.event_description if row.event_description else "",
                    "event_date": row.event_date,
                    "created_at": row.created_at,
                    "documents": []
                }
            if row.doc_id:
                events[eid]["documents"].append({
                    "doc_id": row.doc_id,
                    "fk_case": case_id,
                    "rel_path": row.rel_path if row.rel_path else "",
                    "pdf_title": row.pdf_title if row.pdf_title else "",
                    "summary_ai_html": row.summary_ai_html if row.summary_ai_html else ""
                })
        
        print(f"📄 Found {len(events)} unemailed events")
        
        if not events:
            print("ℹ️  No unemailed events - nothing to email")
            return True
        
        # Count documents with attachments
        total_docs = 0
        attachable_docs = 0
        
        for event_id, event_data in events.items():
            for doc in event_data["documents"]:
                total_docs += 1
                rel_path = doc.get("rel_path", "")
                if rel_path and rel_path != "pending":
                    # Check if file actually exists
                    base_docs_dir = r"\\10.146.176.84\general\docketwatch\docs"
                    full_path = os.path.join(base_docs_dir, rel_path)
                    if os.path.exists(full_path):
                        attachable_docs += 1
                        print(f"   ✅ Attachable: {doc['pdf_title']} ({doc['doc_id']})")
                    else:
                        print(f"   ❌ Missing file: {full_path}")
                else:
                    print(f"   ⏳ Pending: {doc['pdf_title']} ({doc['doc_id']})")
        
        print(f"📎 {attachable_docs} of {total_docs} documents can be attached")
        
        # Get celebrities
        cursor.execute("""
            SELECT e.name AS celebrity_name
            FROM docketwatch.dbo.celebrities e
            INNER JOIN docketwatch.dbo.case_celebrity_matches m ON m.fk_celebrity = e.id
            WHERE m.fk_case = ?
        """, (case_id,))
        
        celebs = [row.celebrity_name for row in cursor.fetchall()]
        print(f"🌟 Found celebrities: {', '.join(celebs) if celebs else 'None'}")
        
        cursor.close()
        conn.close()
        
        print("✅ Test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

if __name__ == "__main__":
    case_id = sys.argv[1] if len(sys.argv) > 1 else "107756"
    test_main_alert(case_id)