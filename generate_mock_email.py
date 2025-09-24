#!/usr/bin/env python3
"""Generate mock HTML for final email format test."""

from datetime import datetime

# URLs
INTERNAL_URL_BASE = 'https://docketwatch.com/case/'
DOCS_BASE_URL = 'https://docketwatch.com/docs'

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

def generate_mock_email():
    """Generate mock email HTML with comprehensive test data."""
    
    # Create mock data for testing with various scenarios
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
                    'whats_next': 'The defendant has 30 days to respond, and oral arguments are expected within 60 days',
                    'summary': ''
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
                    'whats_next': '',
                    'summary': ''
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
                    'whats_next': '',
                    'summary': ''
                }
            ]
        },
        102: {
            'event_description': 'Response to Motion Filed',
            'event_date': datetime(2024, 1, 20),
            'created_at': datetime(2024, 1, 20, 9, 15),
            'documents': [
                {
                    'doc_id': '12348',
                    'fk_case': '987',
                    'pdf_title': 'Opposition to Motion for Summary Judgment',
                    'rel_path': 'docs/987/opposition.pdf',
                    'pdf_type': 'Docket',
                    'event_summary': 'The defendant strongly opposes the motion for summary judgment, arguing that there are material issues of fact that require a jury trial.',
                    'newsworthiness': 'Yes',
                    'newsworthiness_reason': 'The response includes bombshell allegations that could change the entire case',
                    'story_headline': 'SHOCKING COUNTER-ALLEGATIONS ROCK CELEBRITY LAWSUIT',
                    'story_sub_head': 'Defense fires back with explosive claims of misconduct and fraud',
                    'story_body': 'The defendant has fired back with explosive counter-allegations in their response to the summary judgment motion, claiming the plaintiff engaged in fraudulent conduct and breach of fiduciary duty.\n\nThe 52-page filing includes previously unseen communications that allegedly show a pattern of deceptive behavior. "This completely changes the landscape of this case," said a legal expert familiar with the matter.',
                    'whats_next': 'Oral arguments are scheduled for next month, and the judge may order additional discovery',
                    'summary': ''
                }
            ]
        }
    }
    
    case_number = "2:24-cv-00123"
    case_name = "Celebrity Plaintiff v. Media Company LLC"
    celebs = "Taylor Swift, Kim Kardashian"
    case_id = "987"
    case_summary = "This high-profile defamation lawsuit involves allegations of false statements made in a widely-circulated article about celebrity business dealings. The case has drawn significant media attention due to the prominence of the parties involved and the substantial damages being sought."
    case_url = "https://court.example.com/case/987"
    
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
    
    print(f"✅ Mock email HTML generated successfully!")
    print(f"📊 Stats:")
    print(f"   - Case: {case_number}")
    print(f"   - Events: {len(events)}")
    print(f"   - Total documents: {sum(len(event['documents']) for event in events.values())}")
    print(f"   - Attachments: {attachment_count}")
    print(f"📁 Output saved to: test_final_email_output.html")

if __name__ == "__main__":
    generate_mock_email()