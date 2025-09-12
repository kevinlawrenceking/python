#!/usr/bin/env python3
"""
Single Case Event Pipeline Runner
Runs the complete RSS trigger pipeline on a single case event.

Usage: python single_case_event_pipeline.py <case_id> <event_no> <court_code>

Example: python single_case_event_pipeline.py 12345 67 cacd
"""

import sys
import os
import pyodbc
from datetime import datetime

# Import the process_new_event function from your RSS trigger
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from docketwatch_rss_trigger import process_new_event
from scraper_base import log_message


def main():
    """Main function to run pipeline on single case event"""
    
    if len(sys.argv) != 4:
        print("❌ ERROR: Invalid arguments")
        print("")
        print("📋 USAGE:")
        print("   python single_case_event_pipeline.py <case_id> <event_no> <court_code>")
        print("")
        print("📝 EXAMPLES:")
        print("   python single_case_event_pipeline.py 12345 67 cacd")
        print("   python single_case_event_pipeline.py 98765 123 nysd")
        print("")
        print("💡 PARAMETERS:")
        print("   case_id    - The database ID of the case")
        print("   event_no   - The event number to process")
        print("   court_code - The court code (e.g., cacd, nysd, flsd)")
        return 1
    
    try:
        case_id = int(sys.argv[1])
        event_no = int(sys.argv[2])
        court_code = sys.argv[3].lower()
    except ValueError:
        print("❌ ERROR: case_id and event_no must be integers")
        return 1
    
    print("🚀 SINGLE CASE EVENT PIPELINE RUNNER")
    print("=" * 50)
    print(f"📋 Case ID: {case_id}")
    print(f"📋 Event No: {event_no}")
    print(f"📋 Court Code: {court_code}")
    print(f"📋 Started: {datetime.now()}")
    print("=" * 50)
    
    # Validate case exists
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, case_name, case_number 
            FROM docketwatch.dbo.cases 
            WHERE id = ?
        """, (case_id,))
        
        case_row = cursor.fetchone()
        if not case_row:
            print(f"❌ ERROR: Case ID {case_id} not found in database")
            return 1
        
        case_name = case_row[1] or "Unknown Case"
        case_number = case_row[2] or "Unknown Number"
        
        print(f"✅ Found case: {case_name} ({case_number})")
        
        # Check if event exists
        cursor.execute("""
            SELECT id, event_description, stage_completed
            FROM docketwatch.dbo.case_events 
            WHERE fk_cases = ? AND event_no = ?
        """, (case_id, event_no))
        
        event_row = cursor.fetchone()
        if event_row:
            print(f"✅ Found event: {event_row[1][:100]}...")
            print(f"📊 Current stage: {event_row[2] or 0}")
        else:
            print(f"⚠️  WARNING: Event {event_no} not found - pipeline will create if needed")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ ERROR: Database validation failed: {e}")
        return 1
    
    print("\n🔄 STARTING PIPELINE...")
    print("-" * 30)
    
    try:
        # Run the complete pipeline using your existing function
        process_new_event(fk_case=case_id, event_no=event_no, court_code=court_code)
        
        print("\n✅ PIPELINE COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print("📊 What was processed:")
        print("   1. ✅ PACER scrape refresh")
        print("   2. ✅ Event enrichment")
        print("   3. ✅ Document synchronization")
        print("   4. ✅ PDF download")
        print("   5. ✅ OCR processing")
        print("   6. ✅ AI summarization")
        print("   7. ✅ Status tracking")
        
        # Show final status
        try:
            conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            conn.setencoding(encoding='utf-8')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT stage_completed, event_description
                FROM docketwatch.dbo.case_events 
                WHERE fk_cases = ? AND event_no = ?
            """, (case_id, event_no))
            
            final_row = cursor.fetchone()
            if final_row:
                stage_names = {
                    0: "Created",
                    1: "PACER Enriched", 
                    2: "Documents Synced",
                    3: "PDFs Downloaded",
                    4: "OCR Complete",
                    5: "Summarized"
                }
                final_stage = final_row[0] or 0
                stage_name = stage_names.get(final_stage, f"Stage {final_stage}")
                print(f"\n📊 Final Status: {stage_name} ({final_stage})")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"⚠️  WARNING: Could not check final status: {e}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {e}")
        print("=" * 50)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
