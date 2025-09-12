#!/usr/bin/env python3
"""
Simple duplicate analysis
"""

import pyodbc

def main():
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print("✅ Database connected")
        
        # Check for any duplicates based on case + event_no only
        print("\n=== Checking for duplicate case/event_no pairs ===")
        cursor.execute("""
            SELECT 
                fk_cases,
                event_no,
                COUNT(*) as count,
                MIN(created_at) as first_created,
                MAX(created_at) as last_created,
                STRING_AGG(event_description, ' | ') as descriptions
            FROM docketwatch.dbo.case_events 
            WHERE CONVERT(date, created_at) = CONVERT(date, GETDATE())
            GROUP BY fk_cases, event_no
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
        """)
        
        rows = cursor.fetchall()
        if rows:
            print(f"⚠️  Found {len(rows)} case/event_no pairs with multiple entries:")
            for row in rows:
                fk_case, event_no, count, first, last, descriptions = row
                print(f"   Case {fk_case}, Event {event_no}: {count} entries")
                print(f"   First: {first}, Last: {last}")
                print(f"   Descriptions: {descriptions}")
                
                # Get case name
                cursor.execute("SELECT case_name FROM docketwatch.dbo.cases WHERE id = ?", (fk_case,))
                case_row = cursor.fetchone()
                if case_row:
                    print(f"   Case Name: {case_row[0]}")
                print()
        else:
            print("✅ No duplicate case/event_no pairs found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
