#!/usr/bin/env python3
"""
Test script for the clean, simple baseline email formatting.
"""
import sys
import os
from datetime import datetime

# Add the current directory to Python path so we can import the main script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the updated build_email_html function
from docketwatch_case_events_alert_plus2 import build_email_html

def test_simple_baseline():
    """Test the simple baseline email formatting."""
    
    # Sample test data
    case_number = "1:23-cv-10628-JGLC"
    case_name = "Doe v. Combs et al"
    celebs = "Sean Combs"
    case_id = 107756
    case_url = "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?611545"
    case_summary = "This sexual assault lawsuit stems from allegations dating back to 2003, filed under New York's Adult Survivors Act."
    
    # Sample event data with simple AI summary
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
                    "summary": "<p>In a letter filed on September 22, 2025, attorneys for defendants Sean Combs and Harve Pierre responded to a court order regarding the scope of discovery in the sexual assault lawsuit.</p>"
                }
            ]
        }
    }
    
    print("🔄 Testing simple baseline email format...")
    
    try:
        # Generate the HTML email
        html_output = build_email_html(case_number, case_name, celebs, case_id, case_summary, events, case_url)
        
        # Save the output for inspection
        output_file = "test_simple_baseline_output.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_output)
        
        print(f"✅ Email HTML generated successfully!")
        print(f"📄 Output saved to: {output_file}")
        
        # Basic validation checks
        if '<h3>TMZ Case Update:' in html_output:
            print("✅ Simple header format")
        
        if '<b>Celebrities involved:</b>' in html_output:
            print("✅ Celebrity section")
        
        if '<hr/>' in html_output:
            print("✅ Basic HR separators")
        
        if 'DocketWatch</a>' in html_output:
            print("✅ Links included")
        
        if case_summary in html_output:
            print("✅ Case summary included")
        
        # Check that it's truly simple (no complex styling)
        complex_styles = ['border-left:', 'background-color:', 'font-family:']
        has_complex_styles = any(style in html_output for style in complex_styles)
        
        if not has_complex_styles:
            print("✅ Clean and simple (no complex styling)")
        else:
            print("⚠️  Still has some complex styling")
        
        print(f"\n📄 Simple baseline email format test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing email format: {e}")
        return False

if __name__ == "__main__":
    success = test_simple_baseline()
    if success:
        print(f"\n🎉 Simple baseline format is working!")
    else:
        print(f"\n💥 Test failed!")
        sys.exit(1)