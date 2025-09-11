#!/usr/bin/env python3
"""
Quick reset script for RSS testing
Removes today's RSS entries and related records for specific cases
"""

import pyodbc
from datetime import datetime

def reset_rss_testing(pacer_ids=None, reset_all_today=False):
    """
    Reset RSS entries for testing
    
    Args:
        pacer_ids: List of specific pacer_ids to reset, or None
        reset_all_today: If True, reset all today's entries (dangerous!)
    """
    
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        if pacer_ids:
            print(f"Resetting RSS data for pacer_ids: {pacer_ids}")
            placeholders = ','.join(['?' for _ in pacer_ids])
            
            # Get fk_case values
            cursor.execute(f"""
                SELECT pacer_id, id as fk_case 
                FROM docketwatch.dbo.cases 
                WHERE pacer_id IN ({placeholders})
            """, pacer_ids)
            
            case_mapping = {row.pacer_id: row.fk_case for row in cursor.fetchall()}
            fk_cases = list(case_mapping.values())
            
            if not fk_cases:
                print("No matching cases found!")
                return
                
            print(f"Found cases: {case_mapping}")
            
            # Delete today's documents
            fk_placeholders = ','.join(['?' for _ in fk_cases])
            cursor.execute(f"""
                DELETE FROM docketwatch.dbo.documents 
                WHERE fk_case IN ({fk_placeholders})
                  AND CAST(date_downloaded AS DATE) = ?
            """, fk_cases + [today])
            docs_deleted = cursor.rowcount
            
            # Delete today's case_events
            cursor.execute(f"""
                DELETE FROM docketwatch.dbo.case_events 
                WHERE fk_cases IN ({fk_placeholders})
                  AND CAST(created_at AS DATE) = ?
            """, fk_cases + [today])
            events_deleted = cursor.rowcount
            
            # Delete today's RSS entries
            cursor.execute(f"""
                DELETE FROM docketwatch.dbo.rss_feed_entries 
                WHERE pacer_id IN ({placeholders})
                  AND CAST(pub_date AS DATE) = ?
            """, pacer_ids + [today])
            rss_deleted = cursor.rowcount
            
            conn.commit()
            print(f"✅ Reset complete!")
            print(f"   Documents deleted: {docs_deleted}")
            print(f"   Events deleted: {events_deleted}")
            print(f"   RSS entries deleted: {rss_deleted}")
            
        elif reset_all_today:
            print("⚠️  WARNING: This will reset ALL today's RSS data!")
            confirm = input("Type 'YES' to confirm: ")
            if confirm != 'YES':
                print("Reset cancelled.")
                return
                
            # Delete all today's data
            cursor.execute("DELETE FROM docketwatch.dbo.documents WHERE CAST(date_downloaded AS DATE) = ?", (today,))
            docs_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM docketwatch.dbo.case_events WHERE CAST(created_at AS DATE) = ?", (today,))
            events_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM docketwatch.dbo.rss_feed_entries WHERE CAST(pub_date AS DATE) = ?", (today,))
            rss_deleted = cursor.rowcount
            
            conn.commit()
            print(f"✅ Full reset complete!")
            print(f"   Documents deleted: {docs_deleted}")
            print(f"   Events deleted: {events_deleted}")
            print(f"   RSS entries deleted: {rss_deleted}")
        else:
            # Just show what would be reset
            cursor.execute("""
                SELECT DISTINCT rfe.pacer_id, c.case_name, COUNT(*) as entry_count
                FROM docketwatch.dbo.rss_feed_entries rfe
                LEFT JOIN docketwatch.dbo.cases c ON c.pacer_id = rfe.pacer_id
                WHERE CAST(rfe.pub_date AS DATE) = ?
                GROUP BY rfe.pacer_id, c.case_name
                ORDER BY entry_count DESC
            """, (today,))
            
            cases = cursor.fetchall()
            if cases:
                print(f"RSS entries from today ({today}):")
                for case in cases:
                    print(f"  pacer_id={case.pacer_id}, case={case.case_name}, entries={case.entry_count}")
                print(f"\nTo reset specific cases, call:")
                print(f"reset_rss_testing([{', '.join(str(c.pacer_id) for c in cases[:3])}])")
            else:
                print("No RSS entries found for today.")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command line usage: python reset_rss.py 12345 67890
        pacer_ids = [int(x) for x in sys.argv[1:]]
        reset_rss_testing(pacer_ids)
    else:
        # Interactive mode - show what can be reset
        reset_rss_testing()
