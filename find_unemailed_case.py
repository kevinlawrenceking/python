#!/usr/bin/env python3
import pyodbc

def find_case_with_unemailed_events():
    """Find a case with unemailed events that has documents."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print("🔍 Looking for cases with unemailed events that have documents...")
        print("=" * 60)
        
        # Find cases with unemailed events that have documents
        cursor.execute("""
            SELECT TOP 5 
                c.id,
                c.case_number,
                c.case_name,
                COUNT(e.id) as unemailed_events,
                COUNT(d.doc_id) as total_documents
            FROM docketwatch.dbo.cases c
            INNER JOIN docketwatch.dbo.case_events e ON c.id = e.fk_cases
            LEFT JOIN docketwatch.dbo.documents d ON e.id = d.fk_case_event
            WHERE e.emailed = 0
            GROUP BY c.id, c.case_number, c.case_name
            HAVING COUNT(d.doc_id) > 0
            ORDER BY COUNT(d.doc_id) DESC
        """)
        
        cases = cursor.fetchall()
        
        if not cases:
            print("❌ No cases found with unemailed events that have documents")
            return None
        
        print(f"📄 Found {len(cases)} cases with unemailed events:")
        print()
        
        for case in cases:
            case_id, case_number, case_name, unemailed_events, total_docs = case
            print(f"📋 Case {case_id}: {case_number}")
            print(f"   Name: {case_name[:80]}...")
            print(f"   Unemailed events: {unemailed_events}")
            print(f"   Documents: {total_docs}")
            
            # Check if documents have valid paths
            cursor.execute("""
                SELECT COUNT(*) 
                FROM docketwatch.dbo.documents d
                INNER JOIN docketwatch.dbo.case_events e ON d.fk_case_event = e.id
                WHERE e.fk_cases = ? 
                AND e.emailed = 0 
                AND d.rel_path IS NOT NULL 
                AND d.rel_path != 'pending'
            """, (case_id,))
            
            downloadable_docs = cursor.fetchone()[0]
            print(f"   Downloadable docs: {downloadable_docs}")
            print()
        
        # Return the first case with downloadable documents
        best_case = cases[0]
        cursor.close()
        conn.close()
        
        return best_case.id
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    case_id = find_case_with_unemailed_events()
    if case_id:
        print(f"🎯 Best test case: {case_id}")
    else:
        print("❌ No suitable test case found")