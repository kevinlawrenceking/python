#!/usr/bin/env python3
import sys
import os

# Add the same imports as the main script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_sample_email_html():
    """Create a sample email HTML to preview the new formatting."""
    
    # Sample data based on your example
    case_number = "1:23-cv-10628-JGLC"
    case_name = "Doe v. Combs et al"
    celebs = "Sean Combs"
    case_id = 107756
    case_summary = "High-profile lawsuit involving multiple allegations against entertainment industry figures."
    case_url = "https://example-court-link.com"
    
    # Sample events with enhanced AI summary fields
    events = {
        "ECBEE0BE-9665-42CA-8804-AD61B0548671": {
            "event_description": "Reply Brief Filed",
            "event_date": type('obj', (object,), {'strftime': lambda self, fmt: '2025-09-19'})(),
            "created_at": type('obj', (object,), {'strftime': lambda self, fmt: '2025-09-19 14:30:22'})(),
            "documents": [{
                "doc_id": "127138256058",
                "fk_case": 107756,
                "pdf_title": "Reply Brief - Motion for Pseudonym",
                "rel_path": "cases\\107756\\E127138256058.pdf",
                # Enhanced AI Summary Fields
                "event_summary": "On September 19, 2025, Defendant Jane Doe filed a reply brief arguing she should be allowed to continue using a pseudonym in the lawsuit brought by Shawn Corey Carter.",
                "newsworthiness": "Yes",
                "newsworthiness_reason": "A-list celebrity Shawn 'Jay-Z' Carter is involved in a high-profile lawsuit, and this filing reveals a significant and unusual reversal in legal strategy.",
                "story_headline": "Jay-Z Accuser Fights for Anonymity Rapper Initially Championed",
                "story_sub_head": "\"Jane Doe\" claims Shawn Carter's legal team reversed course to use her mental health against her in ongoing litigation.",
                "story_body": "In a sharp legal turn, the anonymous defendant known as \"Jane Doe\" in Shawn \"Jay-Z\" Carter's lawsuit is accusing the rap mogul of reversing his position on her anonymity in a bid to gain a tactical advantage.\n\nIn a court filing dated September 19, 2025, Doe's attorneys argue that Carter's legal team is now fighting to expose her identity, despite having been the first to ask the court to protect it.\n\nAccording to the filing, Carter's own motion from March 3, 2025, argued that Doe should remain anonymous due to her \"history of mental illness\" and to protect her from \"harmful... media scrutiny.\" Now, Doe claims Carter has changed his tune, arguing that because he believes her allegations are false, she no longer deserves protection.\n\nThe decision now rests with the court on whether to unmask the defendant Carter once sought to shield.",
                "whats_next": "Court will decide whether to grant anonymity protection or expose the defendant's identity."
            }]
        }
    }
    
    # Import the build function (simulate it here)
    INTERNAL_URL_BASE = "https://docketwatch.tmz.tv/court/case_details.cfm?id="
    DOCS_BASE_URL = "https://docketwatch.tmz.tv/docs/cases"
    
    # Build the HTML
    html = f"<h3>TMZ Case Update: {case_number} – {case_name}</h3>"
    if celebs:
        html += f"<p><b>Celebrities involved:</b> {celebs}</p>"
    html += f"<p><b>Internal Link:</b> <a href='{INTERNAL_URL_BASE}{case_id}#dockets'>DocketWatch</a></p>"
    if case_url:
        html += f"<p><b>External Link:</b> <a href='{case_url}'>{case_url}</a></p>"
    
    # Add attachment information
    attachment_count = 1
    if attachment_count > 0:
        html += f"<p><b>📎 {attachment_count} PDF document{'s' if attachment_count > 1 else ''} attached to this email</b></p>"
    
    html += "<hr/>"
    html += f"<p>{len(events)} new case event{'s' if len(events) > 1 else ''} have been added to this case.</p><hr/>"

    for idx, (eid, info) in enumerate(events.items(), start=1):
        html += f"<h4>#{idx} – {info['event_description']}</h4>"
        html += f"<p><b>Event date:</b> {info['event_date'].strftime('%Y-%m-%d')}<br/>"
        html += f"Discovered: {info['created_at'].strftime('%Y-%m-%d %H:%M:%S')}</p>"
        num_docs = len(info['documents'])
        html += f"<p>This event includes {num_docs} document{'s' if num_docs != 1 else ''}.</p>"
        
        # Process documents with enhanced AI summary formatting
        for doc in info['documents']:
            if doc["pdf_title"]:
                rel_path = doc.get("rel_path", "")
                is_attached = rel_path and rel_path != "pending"
                attachment_note = " 📎 (attached)" if is_attached else " (not yet downloaded)"
                html += f"<p><b>{doc['pdf_title']}{attachment_note}</b></p>"
            
            if doc["doc_id"]:
                pdf_link = f"{DOCS_BASE_URL}/{doc['fk_case']}/E{doc['doc_id']}.pdf"
                html += f"<p><a href='{pdf_link}'>Download PDF</a></p>"
            
            # Enhanced AI Summary Section
            has_story = doc.get("story_headline") and doc.get("story_body")
            
            if has_story:
                # TMZ Story Format
                html += "<div style='border: 2px solid #e74c3c; padding: 15px; margin: 10px 0; background-color: #fef9e7;'>"
                html += f"<h3 style='color: #e74c3c; margin-top: 0; font-size: 20px;'>{doc['story_headline']}</h3>"
                
                if doc.get("story_sub_head"):
                    html += f"<h4 style='color: #d35400; font-size: 16px; font-style: italic; margin-bottom: 15px;'>{doc['story_sub_head']}</h4>"
                
                # Format the story body with TMZ-style paragraphs
                story_body = doc.get("story_body", "")
                if story_body:
                    paragraphs = [p.strip() for p in story_body.split('\n\n') if p.strip()]
                    for paragraph in paragraphs:
                        html += f"<p style='line-height: 1.6; margin-bottom: 12px;'>{paragraph}</p>"
                
                # Newsworthiness indicator
                if doc.get("newsworthiness") == "Yes":
                    html += f"<p style='background-color: #e8f5e8; padding: 8px; border-left: 4px solid #27ae60; margin: 10px 0;'>"
                    html += f"<strong>📰 NEWSWORTHY:</strong> {doc.get('newsworthiness_reason', 'High news value')}</p>"
                
                # What's Next section
                if doc.get("whats_next"):
                    html += f"<p style='background-color: #e3f2fd; padding: 8px; border-left: 4px solid #2196f3; margin: 10px 0;'>"
                    html += f"<strong>🔮 WHAT'S NEXT:</strong> {doc['whats_next']}</p>"
                
                html += "</div>"
        
        html += "<hr/>"

    if case_summary:
        html += f"<h4>Case Background Summary</h4><div>{case_summary}</div><hr/>"
    
    return html


def save_sample_email():
    """Save a sample email HTML for preview."""
    
    html_content = create_sample_email_html()
    
    # Wrap in full HTML document for preview
    full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TMZ Case Update Email Preview</title>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
    {html_content}
</body>
</html>
"""
    
    output_file = "email_preview.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"✅ Sample email saved to: {output_file}")
    print("🌐 Open this file in a web browser to preview the enhanced email format")
    
    return output_file

if __name__ == "__main__":
    save_sample_email()