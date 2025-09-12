#!/usr/bin/env python3
"""
Analyze and Fix "Unknown Document Type" Messages
These are PACER error messages that occur when PACER can't resolve document type codes.
"""

import pyodbc
import re
from datetime import datetime

def analyze_unknown_document_types():
    """Analyze the unknown document type pattern and suggest fixes"""
    
    print("🔍 ANALYZING 'UNKNOWN DOCUMENT TYPE' ISSUE")
    print("=" * 60)
    
    print("\n📋 WHAT'S HAPPENING:")
    print("   • These messages come from PACER RSS feeds")
    print("   • PACER encounters document type codes it can't resolve")
    print("   • Examples: 'Unknown Document Type: 16467'")
    print("   • The numbers (16467, 17815, etc.) are internal PACER document type IDs")
    
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        cursor = conn.cursor()
        
        # Get all unknown document type events
        cursor.execute("""
            SELECT 
                id,
                event_description,
                event_date,
                event_url,
                fk_cases
            FROM docketwatch.dbo.case_events 
            WHERE event_description LIKE '%unknown document type%'
            ORDER BY event_date DESC
        """)
        
        unknown_events = cursor.fetchall()
        
        print(f"\n📊 FOUND {len(unknown_events)} EVENTS WITH UNKNOWN DOCUMENT TYPES")
        print("=" * 60)
        
        # Analyze the pattern
        type_codes = []
        case_ids = set()
        
        for event in unknown_events:
            event_id, desc, event_date, event_url, case_id = event
            case_ids.add(case_id)
            
            # Extract the type code number
            match = re.search(r'Unknown Document Type:\s*(\d+)', desc)
            if match:
                type_codes.append(int(match.group(1)))
        
        print(f"\n📈 ANALYSIS:")
        print(f"   • Total events: {len(unknown_events)}")
        print(f"   • Affected cases: {len(case_ids)}")
        print(f"   • Date range: {min(e[2] for e in unknown_events)} to {max(e[2] for e in unknown_events)}")
        print(f"   • Unique type codes: {len(set(type_codes))}")
        
        if type_codes:
            print(f"\n🔢 UNKNOWN TYPE CODES:")
            unique_codes = sorted(set(type_codes))
            for i, code in enumerate(unique_codes[:10], 1):
                count = type_codes.count(code)
                print(f"   {i:2}. {code:6} (appears {count} time{'s' if count != 1 else ''})")
            
            if len(unique_codes) > 10:
                print(f"   ... and {len(unique_codes) - 10} more codes")
        
        print(f"\n💡 SOLUTIONS:")
        print(f"=" * 60)
        
        print(f"\n1️⃣  IGNORE STRATEGY (Recommended)")
        print(f"   • These are PACER system errors, not actionable content")
        print(f"   • Filter them out during RSS processing")
        print(f"   • Don't create case_events for these messages")
        
        print(f"\n2️⃣  ENHANCEMENT STRATEGY")
        print(f"   • Try to resolve type codes via PACER scraping")
        print(f"   • Update event descriptions with actual document info")
        print(f"   • Mark as 'PACER Type Resolution Needed'")
        
        print(f"\n3️⃣  CLEANUP STRATEGY")
        print(f"   • Delete existing unknown document type events")
        print(f"   • They provide no useful information")
        print(f"   • Free up database space")
        
        # Show some recent examples
        print(f"\n📝 RECENT EXAMPLES:")
        print(f"=" * 60)
        
        recent_events = [e for e in unknown_events if e[2].year >= 2022][:5]
        
        for i, event in enumerate(recent_events, 1):
            event_id, desc, event_date, event_url, case_id = event
            print(f"\n{i}. Case {case_id} - {event_date}")
            print(f"   Description: {desc}")
            if event_url:
                print(f"   URL: {event_url[:80]}...")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

def suggest_rss_filter_fix():
    """Suggest code changes to filter out unknown document types"""
    
    print(f"\n🔧 SUGGESTED RSS TRIGGER FIX:")
    print(f"=" * 60)
    
    print(f"""
Add this filter in your RSS trigger where event descriptions are processed:

```python
# In docketwatch_rss_trigger.py, around line 783
event_description_match = re.search(r'\\[(.*?)\\]', desc_raw)
event_description = event_description_match.group(1) if event_description_match else ""

# ADD THIS FILTER:
if event_description.lower().startswith('unknown document type'):
    safe_log(cursor, fk_task_run, "INFO", 
             f"Skipping PACER unknown document type: {{event_description}}", 
             fk_case=fk_case)
    continue  # Skip this RSS item

# Rest of your processing...
```

This will:
✅ Skip unknown document type messages
✅ Log them for monitoring
✅ Prevent cluttering your case_events table
✅ Focus on actionable court documents
""")
    
    print(f"\n🧹 OPTIONAL CLEANUP QUERY:")
    print(f"=" * 60)
    
    print(f"""
To remove existing unknown document type events:

```sql
-- BACKUP FIRST!
SELECT COUNT(*) FROM docketwatch.dbo.case_events 
WHERE event_description LIKE '%unknown document type%';

-- DELETE if you're sure:
DELETE FROM docketwatch.dbo.case_events 
WHERE event_description LIKE '%unknown document type%';
```

⚠️  CAUTION: Backup your database before running DELETE!
""")

if __name__ == "__main__":
    analyze_unknown_document_types()
    suggest_rss_filter_fix()
