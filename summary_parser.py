"""
AI Summary Parser

Parses structured AI summaries into database-ready components.
Extracts event summary, newsworthiness, story elements, key details, and next steps.
"""

import re
from bs4 import BeautifulSoup
import pyodbc


def parse_ai_summary(summary_text):
    """
    Parse the structured AI summary into database-ready components.
    Returns: dict with parsed fields
    """
    result = {
        'event_summary': '',
        'newsworthiness': 'No',
        'newsworthiness_reason': '',
        'story_headline': '',
        'story_sub_head': '',
        'story_body': '',
        'key_details': [],
        'whats_next': ''
    }
    
    try:
        soup = BeautifulSoup(summary_text, 'html.parser')
        
        # Extract EVENT SUMMARY
        event_section = soup.find('h3', string='EVENT SUMMARY')
        if event_section and event_section.find_next_sibling('p'):
            result['event_summary'] = event_section.find_next_sibling('p').get_text().strip()
        
        # Extract NEWSWORTHINESS
        news_section = soup.find('h3', string='NEWSWORTHINESS')
        if news_section:
            news_paras = news_section.find_next_siblings('p')
            for para in news_paras:
                text = para.get_text().strip()
                if text.startswith('Yes -'):
                    result['newsworthiness'] = 'Yes'
                    result['newsworthiness_reason'] = text[5:].strip()
                    break
                elif text.startswith('No -'):
                    result['newsworthiness'] = 'No'
                    result['newsworthiness_reason'] = text[4:].strip()
                    break
        
        # Extract STORY elements
        story_section = soup.find('h3', string='STORY')
        if story_section:
            story_ul = story_section.find_next_sibling('ul')
            if story_ul:
                for li in story_ul.find_all('li'):
                    text = li.get_text().strip()
                    if text.startswith('HEADLINE:'):
                        result['story_headline'] = text[9:].strip()
                    elif text.startswith('SUBHEAD:'):
                        result['story_sub_head'] = text[8:].strip()
                    elif text.startswith('BODY:'):
                        result['story_body'] = text[5:].strip()
        
        # Extract KEY DETAILS
        details_section = soup.find('h3', string='KEY DETAILS')
        if details_section:
            details_ul = details_section.find_next_sibling('ul')
            if details_ul:
                for i, li in enumerate(details_ul.find_all('li')):
                    detail_text = li.get_text().strip()
                    if detail_text and not detail_text.startswith('['):
                        # Try to extract title and detail
                        if ':' in detail_text:
                            parts = detail_text.split(':', 1)
                            key_title = parts[0].strip()
                            key_detail = parts[1].strip()
                        else:
                            key_title = f"Detail {i+1}"
                            key_detail = detail_text
                        
                        result['key_details'].append({
                            'key_title': key_title,
                            'key_detail': key_detail,
                            'sort_order': i+1
                        })
        
        # Extract WHAT'S NEXT
        next_section = soup.find('h3', string="WHAT'S NEXT")
        if next_section and next_section.find_next_sibling('p'):
            result['whats_next'] = next_section.find_next_sibling('p').get_text().strip()
    
    except Exception as e:
        print(f"Warning: Failed to parse AI summary structure: {e}")
    
    return result


def save_structured_summary(cursor, doc_uid, parsed_summary):
    """
    Save the parsed summary components to the database.
    
    Args:
        cursor: Database cursor
        doc_uid: Document GUID
        parsed_summary: Dict from parse_ai_summary()
    """
    
    # Update main document fields
    cursor.execute("""
        UPDATE docketwatch.dbo.documents 
        SET 
            event_summary = ?,
            newsworthiness = ?,
            newsworthiness_reason = ?,
            story_headline = ?,
            story_sub_head = ?,
            story_body = ?,
            whats_next = ?
        WHERE doc_uid = CAST(? AS uniqueidentifier)
    """, (
        parsed_summary['event_summary'][:500],
        parsed_summary['newsworthiness'],
        parsed_summary['newsworthiness_reason'][:200],
        parsed_summary['story_headline'][:200],
        parsed_summary['story_sub_head'][:300],
        parsed_summary['story_body'],
        parsed_summary['whats_next'][:1000],
        doc_uid
    ))
    
    # Clear existing key details for this document
    cursor.execute("""
        DELETE FROM docketwatch.dbo.document_key_details 
        WHERE fk_document_uid = CAST(? AS uniqueidentifier)
    """, (doc_uid,))
    
    # Insert new key details
    for detail in parsed_summary['key_details']:
        cursor.execute("""
            INSERT INTO docketwatch.dbo.document_key_details 
            (fk_document_uid, key_title, key_detail, sort_order)
            VALUES (CAST(? AS uniqueidentifier), ?, ?, ?)
        """, (
            doc_uid,
            detail['key_title'][:100],
            detail['key_detail'][:500],
            detail['sort_order']
        ))


def get_structured_summary(cursor, doc_uid):
    """
    Retrieve structured summary data for a document.
    
    Returns: dict with summary data and key details list
    """
    # Get main summary fields
    cursor.execute("""
        SELECT 
            event_summary, newsworthiness, newsworthiness_reason,
            story_headline, story_sub_head, story_body, whats_next
        FROM docketwatch.dbo.documents 
        WHERE doc_uid = CAST(? AS uniqueidentifier)
    """, (doc_uid,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    result = {
        'event_summary': row[0] or '',
        'newsworthiness': row[1] or 'No',
        'newsworthiness_reason': row[2] or '',
        'story_headline': row[3] or '',
        'story_sub_head': row[4] or '',
        'story_body': row[5] or '',
        'whats_next': row[6] or '',
        'key_details': []
    }
    
    # Get key details
    cursor.execute("""
        SELECT key_title, key_detail, sort_order
        FROM docketwatch.dbo.document_key_details 
        WHERE fk_document_uid = CAST(? AS uniqueidentifier)
        ORDER BY sort_order
    """, (doc_uid,))
    
    for detail_row in cursor.fetchall():
        result['key_details'].append({
            'key_title': detail_row[0],
            'key_detail': detail_row[1],
            'sort_order': detail_row[2]
        })
    
    return result


if __name__ == "__main__":
    # Test parsing with sample data
    sample_html = """
    <h3>EVENT SUMMARY</h3>
    <p>Defendants Sean Combs filed a reply memorandum supporting their motion to dismiss.</p>
    
    <h3>NEWSWORTHINESS</h3>
    <p>Yes - Celebrity involvement and major legal motion in high-profile case</p>
    
    <h3>STORY</h3>
    <ul>
    <li>HEADLINE: Sean Combs Files Reply Brief in Dismissal Motion</li>
    <li>SUBHEAD: Legal team argues plaintiff claims lack factual basis</li>
    <li>BODY: Detailed analysis of the legal arguments...</li>
    </ul>
    
    <h3>KEY DETAILS</h3>
    <ul>
    <li>Filing Type: Reply memorandum in support of motion to dismiss</li>
    <li>Legal Argument: Claims are time-barred and lack factual basis</li>
    <li>Plaintiff Issue: Admits to having no memory of alleged 2006 incident</li>
    </ul>
    
    <h3>WHAT'S NEXT</h3>
    <p>Court will review the motion and schedule a hearing.</p>
    """
    
    result = parse_ai_summary(sample_html)
    print("Parsed Summary:")
    print(f"Event: {result['event_summary']}")
    print(f"Newsworthy: {result['newsworthiness']} - {result['newsworthiness_reason']}")
    print(f"Headline: {result['story_headline']}")
    print(f"Key Details: {len(result['key_details'])} items")
    for detail in result['key_details']:
        print(f"  - {detail['key_title']}: {detail['key_detail']}")