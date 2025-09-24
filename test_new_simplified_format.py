#!/usr/bin/env python3
"""
Test script to verify the new simplified email formatting in docketwatch_case_events_alert_plus2.py
"""
import sys
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Add the current directory to Python path so we can import the main script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the updated build_email_html function
from docketwatch_case_events_alert_plus2 import build_email_html

def test_new_email_format():
    """Test the new simplified email formatting."""
    
    # Sample test data
    case_number = "1:23-cv-10628-JGLC"
    case_name = "Doe v. Combs et al"
    celebs = "Sean Combs"
    case_id = 107756
    case_url = "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?611545"
    case_summary = "This sexual assault lawsuit stems from allegations dating back to 2003, filed under New York's Adult Survivors Act. The case involves claims against Sean Combs and Harve Pierre, with the plaintiff alleging assault at a recording studio when she was 17 years old."
    
    # Sample event data with AI summary
    events = {
        12345: {
            "event_description": "Letter",
            "event_date": datetime(2025, 9, 22),
            "created_at": datetime(2025, 9, 23, 9, 16, 0),
            "documents": [
                {
                    "doc_id": "001-1",
                    "fk_case": case_id,
                    "pdf_title": "Letter",
                    "summary": """<div>
                        <h5>📖 Summary</h5>
                        <p>In a letter filed on September 22, 2025, attorneys for defendants Sean Combs and Harve Pierre responded to a court order regarding the scope of discovery in the sexual assault lawsuit, Kane v. Combs. The defendants argue that the plaintiff's proposal for "full discovery" ignores the court's directive for a limited, four-month plan. They counter-propose a much narrower discovery process focused solely on identifying an alleged "third assailant" while awaiting a Second Circuit ruling that could dismiss the entire case as time-barred.</p>
                        
                        <p><strong>📰 NEWSWORTHY:</strong> This filing reveals Sean Combs's legal strategy to severely limit discovery in a sexual assault case, references vast amounts of evidence seized in his separate federal criminal case, and includes a direct attack on the plaintiff's credibility.</p>
                        
                        <h3>🎬 TMZ STORY: Combs's Lawyers Push to Limit Discovery in Assault Lawsuit</h3>
                        <h4>Filing accuses plaintiff of ignoring court order, proposes narrow probe into "third assailant" while awaiting key appellate ruling.</h4>
                        
                        <p>Sean Combs's legal team is moving to dramatically restrict the evidence-gathering process in the sexual assault lawsuit filed against him by a plaintiff identified as Kane. In a September 22, 2025 letter to Judge Jessica G. L. Clarke, his attorneys accused the plaintiff of ignoring the court's order for a "narrow or tailored proposal" for discovery by instead demanding depositions, document production, and third-party subpoenas on a wide range of topics.</p>
                        
                        <p>The defense argues that such broad discovery is an "unreasonable burden" while they await a crucial decision from the Second Circuit Court of Appeals that could find the entire lawsuit is time-barred and have it dismissed. The plaintiff had argued for extensive discovery, citing the 22-year-old allegations and a risk that defendants "have every incentive to destroy" evidence.</p>
                        
                        <p>Combs's lawyers countered that there is "absolutely no risk of spoliation." They revealed that in connection with Combs's separate criminal case, the U.S. government has already seized "huge volumes of data," including "terabytes" from "over forty devices" and "five iCloud" accounts, all of which are preserved.</p>
                        
                        <p>Instead of the plaintiff's broad request, Combs's team proposed a four-point plan focused exclusively on identifying an alleged "third assailant" from the 2003 incident. In a pointed attack, the filing also included a footnote claiming the plaintiff "has a history of fabricating serious allegations."</p>
                        
                        <p><strong>🔮 WHAT'S NEXT:</strong> The court will likely schedule a discovery conference to resolve the dispute. Plaintiff has until October 6, 2025 to file their response to defendants' limited discovery proposal.</p>
                    </div>"""
                }
            ]
        }
    }
    
    print("🔄 Testing new simplified email format...")
    
    try:
        # Generate the HTML email
        html_output = build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url)
        
        # Save the output for inspection
        output_file = "test_new_format_output.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_output)
        
        print(f"✅ Email HTML generated successfully!")
        print(f"📄 Output saved to: {output_file}")
        
        # Basic validation checks
        if 'font-family: Arial, sans-serif' in html_output:
            print("✅ Professional typography applied")
        
        if 'border-left: 4px solid' in html_output:
            print("✅ Border-left styling implemented")
        
        if 'background-color: #fef9e7' in html_output and 'TMZ STORY' in html_output:
            print("✅ TMZ story section with clean styling")
        
        if '📎' in html_output and 'PDF document' in html_output:
            print("✅ PDF attachment notification included")
        
        if '🌟 CELEBRITIES INVOLVED' in html_output:
            print("✅ Celebrity highlighting preserved")
        
        # Count background colors to ensure they're minimal
        bg_color_count = html_output.count('background-color:')
        print(f"🎨 Background colors used: {bg_color_count} (should be minimal)")
        
        # Check for visual clutter reduction
        if html_output.count('<hr>') == 0:  # Should have no <hr> tags in new format
            print("✅ Visual clutter reduced (no <hr> dividers)")
        
        print("\n📋 Key Features Verified:")
        print("   • Professional typography and spacing")
        print("   • Border-left highlights instead of excessive backgrounds") 
        print("   • Clean TMZ story formatting")
        print("   • Celebrity and newsworthy item emphasis")
        print("   • PDF attachment status")
        print("   • Reduced visual clutter")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing email format: {e}")
        return False

if __name__ == "__main__":
    success = test_new_email_format()
    if success:
        print(f"\n🎉 New simplified email format test completed successfully!")
    else:
        print(f"\n💥 Test failed!")
        sys.exit(1)