#!/usr/bin/env python3
"""Test the final enhanced email format with comprehensive document handling."""

import pyodbc
import sys
from datetime import datetime

# Database connection settings
server = '192.168.1.134'
database = 'CelebMonitor'
username = 'CelebMonitor'
password = 'CelebMonitor1'

# URLs
INTERNAL_URL_BASE = 'https://docketwatch.com/case/'
DOCS_BASE_URL = 'https://docketwatch.com/docs'

def build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url, attachment_count=0):
    """Build enhanced HTML email with comprehensive case information."""
    
    # Header section
    html = f"<div style='font-family: Arial, sans-serif; max-width: 900px;'>"
    html += f"<h2 style='color: #e74c3c; border-bottom: 3px solid #e74c3c; padding-bottom: 10px;'>TMZ Case Update: {case_number}</h2>"
    html += f"<h3 style='color: #2c3e50; margin-top: 0;'>{case_name}</h3>"
    
    if celebs:
        html += f"<p style='background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 15px 0;'>"
        html += f"<strong>🌟 CELEBRITIES INVOLVED:</strong> {celebs}</p>"
    
    # Links section
    html += f"<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;'>"
    html += f"<p><strong>🔗 Links:</strong> "
    html += f"<a href='{INTERNAL_URL_BASE}{case_id}#dockets' style='color: #007bff; text-decoration: none;'>DocketWatch</a>"
    if case_url:
        html += f" | <a href='{case_url}' style='color: #007bff; text-decoration: none;'>Court Website</a>"
    html += "</p>"
    
    # Attachment information
    if attachment_count > 0:
        html += f"<p><strong>📎 {attachment_count} PDF document{'s' if attachment_count > 1 else ''} attached to this email</strong></p>"
    html += "</div>"
    
    # Case summary section (if available)
    if case_summary:
        html += f"<div style='background-color: #e8f4fd; padding: 15px; border-left: 4px solid #2196f3; margin: 20px 0;'>"
        html += f"<h4 style='color: #1976d2; margin-top: 0;'>📋 Case Background Summary</h4>"
        html += f"<div style='line-height: 1.6;'>{case_summary}</div>"
        html += "</div>"

    # Events header
    html += f"<div style='background-color: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0;'>"
    html += f"<h3 style='color: #27ae60; margin: 0;'>📄 {len(events)} New Case Event{'s' if len(events) > 1 else ''}</h3>"
    html += "</div>"

    # Process each event
    for idx, (eid, info) in enumerate(events.items(), start=1):
        html += f"<div style='border: 2px solid #bdc3c7; border-radius: 10px; margin: 25px 0; padding: 0; overflow: hidden;'>"
        
        # Event header
        html += f"<div style='background-color: #34495e; color: white; padding: 15px;'>"
        html += f"<h3 style='margin: 0; font-size: 18px;'>#{idx} – {info['event_description']}</h3>"
        html += f"<p style='margin: 8px 0 0 0; opacity: 0.9;'>"
        html += f"<strong>Event Date:</strong> {info['event_date'].strftime('%B %d, %Y') if info['event_date'] else 'Not specified'} | "
        html += f"<strong>Discovered:</strong> {info['created_at'].strftime('%B %d, %Y at %I:%M %p') if info['created_at'] else 'Unknown'}"
        html += f"</p></div>"
        
        # Document count and types
        num_docs = len(info['documents'])
        docket_docs = [d for d in info['documents'] if d.get('pdf_type') == 'Docket']
        attachment_docs = [d for d in info['documents'] if d.get('pdf_type') == 'Attachment']
        
        html += f"<div style='padding: 15px; background-color: #f8f9fa;'>"
        html += f"<p style='margin: 0; color: #6c757d;'>"
        html += f"<strong>📑 Documents:</strong> {num_docs} total"
        if docket_docs:
            html += f" ({len(docket_docs)} main document{'s' if len(docket_docs) > 1 else ''}"
            if attachment_docs:
                html += f", {len(attachment_docs)} attachment{'s' if len(attachment_docs) > 1 else ''})"
            else:
                html += ")"
        elif attachment_docs:
            html += f" ({len(attachment_docs)} attachment{'s' if len(attachment_docs) > 1 else ''})"
        html += "</p></div>"
        
        # Process main documents first (Docket type)
        main_doc_processed = False
        for doc in docket_docs:
            html += process_document_html(doc, "Main Document", is_main=True)
            main_doc_processed = True
        
        # Process attachments
        for i, doc in enumerate(attachment_docs, 1):
            attachment_label = f"Attachment {i}" if len(attachment_docs) > 1 else "Attachment"
            html += process_document_html(doc, attachment_label, is_main=False)
        
        # If no main document, process other documents
        if not main_doc_processed:
            other_docs = [d for d in info['documents'] if d.get('pdf_type') not in ['Docket', 'Attachment']]
            for i, doc in enumerate(other_docs, 1):
                doc_label = f"Document {i}" if len(other_docs) > 1 else "Document"
                html += process_document_html(doc, doc_label, is_main=True)
        
        html += "</div>"  # Close event container

    html += "</div>"  # Close main container
    return html


def process_document_html(doc, doc_label, is_main=False):
    """Process individual document HTML with enhanced formatting."""
    
    html = f"<div style='padding: 20px; border-top: 1px solid #dee2e6;'>"
    
    # Document header with type and download link
    html += f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>"
    html += f"<h4 style='color: #495057; margin: 0;'>"
    
    # Add icon based on document type
    icon = "📋" if is_main else "📎"
    html += f"{icon} <strong>{doc_label}:</strong> {doc['pdf_title']}"
    
    # Attachment status
    rel_path = doc.get("rel_path", "")
    is_attached = rel_path and rel_path != "pending"
    if is_attached:
        html += " <span style='color: #28a745; font-size: 12px;'>✓ ATTACHED</span>"
    else:
        html += " <span style='color: #ffc107; font-size: 12px;'>⏳ PENDING</span>"
    
    html += "</h4>"
    
    # Download link
    if doc["doc_id"]:
        pdf_link = f"{DOCS_BASE_URL}/{doc['fk_case']}/E{doc['doc_id']}.pdf"
        html += f"<a href='{pdf_link}' style='background-color: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px;'>DOWNLOAD PDF</a>"
    
    html += "</div>"
    
    # Content sections
    event_summary = doc.get("event_summary", "")
    newsworthiness = doc.get("newsworthiness", "")
    has_story = doc.get("story_headline") and doc.get("story_body")
    
    # Main summary (always show if available)
    if event_summary:
        html += f"<div style='background-color: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #6c757d;'>"
        html += f"<h5 style='color: #495057; margin-top: 0;'>📖 Summary</h5>"
        html += f"<p style='line-height: 1.6; margin-bottom: 0;'>{event_summary}</p>"
        html += "</div>"
    
    # Newsworthiness indicator
    if newsworthiness == "Yes":
        reason = doc.get("newsworthiness_reason", "This document has significant news value")
        html += f"<div style='background-color: #d4edda; padding: 12px; border-left: 4px solid #28a745; margin: 15px 0; border-radius: 4px;'>"
        html += f"<p style='margin: 0; color: #155724;'><strong>📰 NEWSWORTHY:</strong> {reason}</p>"
        html += "</div>"
        
        # Full story section (only if newsworthy AND has story content)
        if has_story:
            html += f"<div style='border: 2px solid #e74c3c; padding: 20px; margin: 20px 0; background-color: #fef9e7; border-radius: 8px;'>"
            html += f"<h3 style='color: #e74c3c; margin-top: 0; font-size: 22px; line-height: 1.3;'>{doc['story_headline']}</h3>"
            
            if doc.get("story_sub_head"):
                html += f"<h4 style='color: #d35400; font-size: 16px; font-style: italic; margin-bottom: 20px; font-weight: 500;'>{doc['story_sub_head']}</h4>"
            
            # Format the story body with TMZ-style paragraphs
            story_body = doc.get("story_body", "")
            if story_body:
                paragraphs = [p.strip() for p in story_body.split('\n\n') if p.strip()]
                for paragraph in paragraphs:
                    html += f"<p style='line-height: 1.7; margin-bottom: 16px; font-size: 15px;'>{paragraph}</p>"
            
            # What's Next section
            if doc.get("whats_next"):
                html += f"<div style='background-color: #e3f2fd; padding: 12px; border-left: 4px solid #2196f3; margin: 15px 0; border-radius: 4px;'>"
                html += f"<p style='margin: 0; color: #0d47a1;'><strong>🔮 WHAT'S NEXT:</strong> {doc['whats_next']}</p>"
                html += "</div>"
            
            html += "</div>"
    
    elif newsworthiness == "No":
        html += f"<div style='background-color: #f8d7da; padding: 10px; border-left: 4px solid #dc3545; margin: 15px 0; border-radius: 4px;'>"
        html += f"<p style='margin: 0; color: #721c24; font-size: 14px;'><strong>📝 NOTE:</strong> Document reviewed but not considered newsworthy at this time.</p>"
        html += "</div>"
    
    # Fallback to old summary if no event_summary but has old summary
    elif doc.get("summary") and not event_summary:
        html += f"<div style='background-color: #f4f4f4; padding: 12px; border-radius: 4px; margin: 15px 0;'>"
        html += f"<h5 style='color: #6c757d; margin-top: 0; font-size: 14px;'>Legacy Summary</h5>"
        html += f"<div style='font-size: 14px; line-height: 1.5;'>{doc['summary']}</div>"
        html += "</div>"
    
    html += "</div>"
    return html


def test_email_format():
    """Test the final email format with sample data."""
    print("Testing final comprehensive email format...")
    
    try:
        # Connect to database
        conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Get a case with multiple documents that have AI summaries
        query = """
        SELECT TOP 1 
            c.case_id,
            c.case_number,
            c.case_name,
            c.celebrities,
            c.case_url,
            c.case_summary,
            ce.case_event_id,
            ce.event_description,
            ce.event_date,
            ce.created_at,
            d.document_id,
            d.pdf_title,
            d.rel_path,
            d.pdf_type,
            d.event_summary,
            d.newsworthiness,
            d.newsworthiness_reason,
            d.story_headline,
            d.story_sub_head,
            d.story_body,
            d.whats_next,
            d.summary
        FROM cases c
        JOIN case_events ce ON c.case_id = ce.fk_case
        JOIN documents d ON ce.case_event_id = d.fk_case_event
        WHERE c.celebrities IS NOT NULL
          AND d.event_summary IS NOT NULL
        ORDER BY c.case_id DESC, ce.case_event_id DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("No test data found - creating mock data...")
            
            # Create mock data for testing
            events = {
                101: {
                    'event_description': 'Motion for Summary Judgment Filed',
                    'event_date': datetime(2024, 1, 15),
                    'created_at': datetime(2024, 1, 15, 14, 30),
                    'documents': [
                        {
                            'doc_id': '12345',
                            'fk_case': '987',
                            'pdf_title': 'Motion for Summary Judgment',
                            'rel_path': 'docs/987/motion_summary.pdf',
                            'pdf_type': 'Docket',
                            'event_summary': 'The plaintiff filed a comprehensive motion for summary judgment, arguing that there are no genuine issues of material fact and that they are entitled to judgment as a matter of law.',
                            'newsworthiness': 'Yes',
                            'newsworthiness_reason': 'This represents a significant escalation in the high-profile celebrity litigation',
                            'story_headline': 'CELEBRITY LAWSUIT TAKES DRAMATIC TURN',
                            'story_sub_head': 'High-stakes legal battle reaches critical juncture as summary judgment motion filed',
                            'story_body': 'In a dramatic development that could bring this celebrity legal saga to a swift conclusion, the plaintiff has filed a motion for summary judgment that could end the case without a jury trial.\n\nThe 47-page motion argues that the evidence is so overwhelming that no reasonable jury could rule in favor of the defendant. Legal experts say this is a bold strategic move that shows confidence in the strength of the case.',
                            'whats_next': 'The defendant has 30 days to respond, and oral arguments are expected within 60 days'
                        },
                        {
                            'doc_id': '12346',
                            'fk_case': '987',
                            'pdf_title': 'Exhibit A - Contract Documents',
                            'rel_path': 'docs/987/exhibit_a.pdf',
                            'pdf_type': 'Attachment',
                            'event_summary': 'Supporting documentation including the original contract and related correspondence that forms the basis of the legal dispute.',
                            'newsworthiness': 'No',
                            'newsworthiness_reason': '',
                            'story_headline': '',
                            'story_sub_head': '',
                            'story_body': '',
                            'whats_next': ''
                        },
                        {
                            'doc_id': '12347',
                            'fk_case': '987',
                            'pdf_title': 'Exhibit B - Financial Records',
                            'rel_path': 'pending',
                            'pdf_type': 'Attachment',
                            'event_summary': 'Financial documentation showing the monetary damages claimed in the lawsuit.',
                            'newsworthiness': 'No',
                            'newsworthiness_reason': '',
                            'story_headline': '',
                            'story_sub_head': '',
                            'story_body': '',
                            'whats_next': ''
                        }
                    ]
                }
            }
            
            case_number = "2:24-cv-00123"
            case_name = "Celebrity Plaintiff v. Media Company LLC"
            celebs = "Taylor Swift, Kim Kardashian"
            case_id = "987"
            case_summary = "This high-profile defamation lawsuit involves allegations of false statements made in a widely-circulated article about celebrity business dealings. The case has drawn significant media attention due to the prominence of the parties involved."
            case_url = "https://court.example.com/case/987"
        
        else:
            print(f"Found {len(rows)} documents to test with...")
            
            # Process the real data
            case_data = {}
            events = {}
            
            for row in rows:
                # Extract case info from first row
                if not case_data:
                    case_data = {
                        'case_id': str(row[0]),
                        'case_number': row[1],
                        'case_name': row[2],
                        'celebs': row[3],
                        'case_url': row[4],
                        'case_summary': row[5]
                    }
                
                event_id = row[6]
                if event_id not in events:
                    events[event_id] = {
                        'event_description': row[7],
                        'event_date': row[8],
                        'created_at': row[9],
                        'documents': []
                    }
                
                # Add document
                events[event_id]['documents'].append({
                    'doc_id': str(row[10]),
                    'fk_case': str(row[0]),
                    'pdf_title': row[11] or 'Document',
                    'rel_path': row[12] or 'pending',
                    'pdf_type': row[13] or 'Docket',
                    'event_summary': row[14] or '',
                    'newsworthiness': row[15] or '',
                    'newsworthiness_reason': row[16] or '',
                    'story_headline': row[17] or '',
                    'story_sub_head': row[18] or '',
                    'story_body': row[19] or '',
                    'whats_next': row[20] or '',
                    'summary': row[21] or ''
                })
            
            case_number = case_data['case_number']
            case_name = case_data['case_name']
            celebs = case_data['celebs']
            case_id = case_data['case_id']
            case_summary = case_data['case_summary']
            case_url = case_data['case_url']
        
        # Count attachments
        attachment_count = sum(1 for event in events.values() 
                             for doc in event['documents'] 
                             if doc.get('rel_path') and doc.get('rel_path') != 'pending')
        
        # Generate HTML
        html = build_email_html(case_number, case_name, celebs, case_id, case_summary, 
                               events, case_url, attachment_count)
        
        # Save to file
        with open('u:\\docketwatch\\python\\test_final_email_output.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Email HTML generated successfully!")
        print(f"📊 Stats:")
        print(f"   - Case: {case_number}")
        print(f"   - Events: {len(events)}")
        print(f"   - Total documents: {sum(len(event['documents']) for event in events.values())}")
        print(f"   - Attachments: {attachment_count}")
        print(f"📁 Output saved to: test_final_email_output.html")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_email_format()