#!/usr/bin/env python3
"""
Analyze PACER case event HTML to identify unique identifiers.
"""

def analyze_pacer_event_html():
    """Analyze the PACER HTML structure for unique identifiers"""
    
    # Sample PACER HTML row
    pacer_html = '''
    <tr>
        <td width="94" valign="top" nowrap="">09/11/2025</td>
        <td style="white-space:nowrap" valign="top" align="right">
            <a href="https://ecf.nysd.uscourts.gov/doc1/127138195871" 
               onclick="goDLS('/doc1/127138195871','575772','240','','2','1','','','');return(false);">73</a>&nbsp;
        </td>
        <td valign="top">
            <!--SB-->FIRST AMENDED COMPLAINT amending 
            <a href="https://ecf.nysd.uscourts.gov/doc1/127130777053" 
               onclick="goDLS('/doc1/127130777053','575772','6','','2','1','','','');return(false);">1</a> 
            Complaint, against Ira Bernstein, Debmar-Mercury LLC, John and Jane Doe 1-5, Mort Marcus with JURY DEMAND.
            Document filed by Kelvin Hunter. Related document: 
            <a href="https://ecf.nysd.uscourts.gov/doc1/127130777053" 
               onclick="goDLS('/doc1/127130777053','575772','6','','2','1','','','');return(false);">1</a> 
            Complaint,.(sgz) (Entered: 09/11/2025)
        </td>
    </tr>
    '''
    
    print("🔍 PACER EVENT UNIQUE IDENTIFIER ANALYSIS")
    print("=" * 60)
    
    print("\n📋 AVAILABLE IDENTIFIERS IN PACER HTML:")
    print("-" * 40)
    
    identifiers = [
        {
            "name": "Document Number",
            "value": "73",
            "location": "Second <td>, anchor text",
            "uniqueness": "Unique per case",
            "stability": "Permanent",
            "reliability": "⭐⭐⭐⭐⭐",
            "notes": "Most reliable - PACER's official document number"
        },
        {
            "name": "Document URL/ID", 
            "value": "127138195871",
            "location": "href='/doc1/127138195871'",
            "uniqueness": "Globally unique",
            "stability": "Permanent",
            "reliability": "⭐⭐⭐⭐⭐",
            "notes": "PACER's internal document ID - globally unique"
        },
        {
            "name": "Case Number in goDLS",
            "value": "575772", 
            "location": "onclick goDLS second parameter",
            "uniqueness": "Case-specific",
            "stability": "Permanent",
            "reliability": "⭐⭐⭐⭐",
            "notes": "PACER's internal case identifier"
        },
        {
            "name": "Event Date",
            "value": "09/11/2025",
            "location": "First <td>",
            "uniqueness": "Not unique",
            "stability": "Can change",
            "reliability": "⭐⭐",
            "notes": "Multiple events can have same date"
        },
        {
            "name": "Event Description Hash",
            "value": "MD5/SHA of description",
            "location": "Third <td> content",
            "uniqueness": "Usually unique",
            "stability": "Can change",
            "reliability": "⭐⭐⭐",
            "notes": "Calculated from description text"
        }
    ]
    
    for i, identifier in enumerate(identifiers, 1):
        print(f"\n{i}. {identifier['name']}")
        print(f"   Value: {identifier['value']}")
        print(f"   Location: {identifier['location']}")
        print(f"   Uniqueness: {identifier['uniqueness']}")
        print(f"   Stability: {identifier['stability']}")
        print(f"   Reliability: {identifier['reliability']}")
        print(f"   Notes: {identifier['notes']}")
    
    print("\n" + "=" * 60)
    print("🎯 RECOMMENDED APPROACH")
    print("=" * 60)
    
    print("\n✅ PRIMARY IDENTIFIER: Document Number (73)")
    print("   - Most natural and expected")
    print("   - Used consistently across PACER")
    print("   - What lawyers and users reference")
    print("   - Available in RSS feeds")
    
    print("\n✅ SECONDARY IDENTIFIER: Document URL ID (127138195871)")
    print("   - Globally unique across all PACER")
    print("   - Never changes once assigned")
    print("   - Can extract from href attributes")
    print("   - Perfect fallback for edge cases")
    
    print("\n🛡️ ROBUST DUPLICATE DETECTION STRATEGY:")
    print("   1. Use Document Number as primary key")
    print("   2. Extract Document URL ID as secondary identifier")  
    print("   3. Combine with existing criteria:")
    print("      - fk_cases (same case)")
    print("      - event_date (same date)")
    print("      - document_number (PACER doc #)")
    print("      - document_url_id (PACER internal ID)")
    
    return {
        "primary_id": "document_number",
        "secondary_id": "document_url_id", 
        "extraction_needed": True
    }


def suggest_database_changes():
    """Suggest database schema changes for unique identifiers"""
    
    print("\n" + "=" * 60)
    print("📊 DATABASE SCHEMA RECOMMENDATIONS")
    print("=" * 60)
    
    schema_changes = [
        {
            "table": "case_events",
            "new_columns": [
                "pacer_document_number INT NULL",
                "pacer_document_url_id VARCHAR(50) NULL", 
                "pacer_case_id VARCHAR(20) NULL"
            ],
            "indexes": [
                "CREATE INDEX IX_case_events_pacer_doc_num ON case_events (fk_cases, pacer_document_number)",
                "CREATE UNIQUE INDEX IX_case_events_pacer_url_id ON case_events (pacer_document_url_id) WHERE pacer_document_url_id IS NOT NULL"
            ]
        }
    ]
    
    for change in schema_changes:
        print(f"\n🗄️ Table: {change['table']}")
        print("   New Columns:")
        for col in change['new_columns']:
            print(f"      {col}")
        print("   Recommended Indexes:")
        for idx in change['indexes']:
            print(f"      {idx}")
    
    print("\n🔄 UPDATED DUPLICATE DETECTION LOGIC:")
    print("""
    # New robust approach with PACER identifiers
    if pacer_document_number:
        # Use PACER document number (most reliable)
        cursor.execute('''
            SELECT id FROM case_events 
            WHERE fk_cases = ? AND pacer_document_number = ?
        ''', (fk_case, pacer_document_number))
    elif pacer_document_url_id:
        # Use PACER URL ID (globally unique)
        cursor.execute('''
            SELECT id FROM case_events 
            WHERE pacer_document_url_id = ?
        ''', (pacer_document_url_id,))
    else:
        # Fallback to existing criteria
        cursor.execute('''
            SELECT id FROM case_events 
            WHERE fk_cases = ? AND CAST(event_date AS DATE) = CAST(? AS DATE)
              AND event_no = ? AND LEFT(event_description, 10) = ?
        ''', (fk_case, event_date, event_no, desc_prefix))
    """)


if __name__ == "__main__":
    recommendation = analyze_pacer_event_html()
    suggest_database_changes()
    
    print("\n🎉 CONCLUSION:")
    print("✅ Extract Document Number (73) and Document URL ID (127138195871)")
    print("✅ Add new columns to case_events table")  
    print("✅ Update duplicate detection to use PACER identifiers")
    print("✅ This will provide bulletproof duplicate prevention!")
