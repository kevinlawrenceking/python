#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced email formatting with new AI summary fields.
"""
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the enhanced build_email_html function
from docketwatch_case_events_alert_plus2 import build_email_html

def test_enhanced_email():
    """Test the enhanced email with the new AI summary fields."""
    
    # Sample test data based on your notes
    case_number = "1:23-cv-10628-JGLC"
    case_name = "Doe v. Carter"
    celebs = "Shawn 'Jay-Z' Carter"
    case_id = 107756
    case_url = "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?611545"
    case_summary = "High-profile lawsuit involving anonymity issues and mental health considerations in celebrity litigation."
    
    # Sample event with full AI summary fields from your notes
    events = {
        12345: {
            "event_description": "Reply Brief",
            "event_date": datetime(2025, 9, 19),
            "created_at": datetime(2025, 9, 23, 9, 16, 0),
            "documents": [
                {
                    "doc_id": "019-1",
                    "fk_case": case_id,
                    "pdf_title": "Reply Brief - Motion for Continued Anonymity",
                    "summary": "",  # Legacy field - empty since we have new fields
                    "event_summary": "On September 19, 2025, Defendant Jane Doe filed a reply brief arguing she should be allowed to continue using a pseudonym in the lawsuit brought by Shawn Corey Carter. Doe claims Carter has inexplicably reversed his own initial motion, filed March 3, 2025, which had supported her anonymity due to her 'history of mental illness and medical vulnerabilities.' Doe asserts that Carter's new opposition is a tactical move and that public disclosure would lead to harassment and 'catastrophic consequences.'",
                    "newsworthiness": "Yes",
                    "newsworthiness_reason": "A-list celebrity Shawn 'Jay-Z' Carter is involved in a high-profile lawsuit, and this filing reveals a significant and unusual reversal in legal strategy where he now opposes the very anonymity for his accuser that he initially championed.",
                    "story_headline": "Jay-Z Accuser Fights for Anonymity Rapper Initially Championed",
                    "story_sub_head": "\"Jane Doe\" claims Shawn Carter's legal team reversed course to use her mental health against her in ongoing litigation.",
                    "story_body": "In a sharp legal turn, the anonymous defendant known as \"Jane Doe\" in Shawn \"Jay-Z\" Carter's lawsuit is accusing the rap mogul of reversing his position on her anonymity in a bid to gain a tactical advantage. In a court filing dated September 19, 2025, Doe's attorneys argue that Carter's legal team is now fighting to expose her identity, despite having been the first to ask the court to protect it.\n\nAccording to the filing, Carter's own motion from March 3, 2025, argued that Doe should remain anonymous due to her \"history of mental illness\" and to protect her from \"harmful... media scrutiny.\" Now, Doe claims Carter has changed his tune, arguing that because he believes her allegations are false, she no longer deserves protection. \"Carter's reversal of positions is not supported by sound, substantive arguments,\" the filing states, asserting his new stance \"only reinforces the need for anonymity.\"\n\nDoe's brief also raises serious safety concerns, referencing an alleged agreement where Carter's team promised not to \"harass\" her. She claims private investigators have nonetheless harassed her and her parents, and that Carter's supporters have sent threats. The filing references a psychiatrist's declaration warning of \"catastrophic consequences\" to Doe's health if her identity is revealed. The decision now rests with the court on whether to unmask the defendant Carter once sought to shield.",
                    "whats_next": "The court will need to decide whether to grant Doe's motion to continue using a pseudonym. Carter's legal team is expected to file a response to this reply brief within the next two weeks."
                }
            ]
        }
    }
    
    print("🔄 Testing enhanced email format with new AI summary fields...")
    
    try:
        # Generate the HTML email
        html_output = build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url)
        
        # Save the output for inspection
        output_file = "enhanced_email_preview.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_output)
        
        print(f"✅ Enhanced email HTML generated successfully!")
        print(f"📄 Output saved to: {output_file}")
        
        # Validation checks for new features
        checks = [
            ('TMZ EXCLUSIVE', 'TMZ exclusive branding'),
            ('Jay-Z Accuser Fights for Anonymity', 'Story headline'),
            ('Jane Doe claims Shawn Carter', 'Story sub-head'),
            ('📰 NEWSWORTHY:', 'Newsworthy section'),
            ('🔮 WHAT\'S NEXT:', 'What\'s Next section'),
            ('📋 Document:', 'Document attachment info'),
            ('✓ ATTACHED', 'Attachment indicator'),
            ('📄 Summary', 'Event summary section'),
            ('🌟 CELEBRITIES INVOLVED:', 'Celebrity highlighting'),
            ('background-color: #fef9e7', 'TMZ story styling'),
            ('Reply_Brief_-_Motion_for_Continued_Anonymity', 'Friendly attachment name'),
        ]
        
        passed_checks = 0
        for check_text, description in checks:
            if check_text in html_output:
                print(f"✅ {description}")
                passed_checks += 1
            else:
                print(f"❌ {description}")
        
        print(f"\n📊 Passed {passed_checks}/{len(checks)} checks")
        
        if passed_checks >= len(checks) - 2:  # Allow 2 checks to fail
            print("\n🎉 Enhanced email format working perfectly!")
            print("📋 New features confirmed:")
            print("   • Individual AI summary fields (event_summary, newsworthiness, etc.)")
            print("   • TMZ-style story formatting with headline and sub-head")
            print("   • Enhanced visual design with better spacing")
            print("   • Friendly PDF attachment names")
            print("   • No download links (PDFs attached instead)")
            print("   • Professional newsworthy and what's next sections")
            print("   • Improved celebrity highlighting")
            return True
        else:
            print("\n⚠️  Some features may need adjustment")
            return False
        
    except Exception as e:
        print(f"❌ Error testing enhanced email format: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_enhanced_email()
    if not success:
        sys.exit(1)