#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Import the build_email_html function
from docketwatch_case_events_alert_plus2 import build_email_html
from datetime import datetime

# Mock data to test the clean formatting
mock_events = {
    "12345": {
        "event_description": "Motion for Summary Judgment Filed",
        "event_date": datetime(2024, 9, 23),
        "created_at": datetime(2024, 9, 23, 14, 30),
        "documents": [{
            "pdf_title": "Motion for Summary Judgment",
            "event_summary": "Defendant's motion for summary judgment argues that there are no genuine disputes of material fact and that they are entitled to judgment as a matter of law.",
            "newsworthiness": "High",
            "newsworthiness_reason": "This motion could potentially end the high-profile case if granted by the court.",
            "story_headline": "BOMBSHELL LEGAL MOVE: Defendant Files Motion That Could End Celebrity Lawsuit",
            "story_sub_head": "High-stakes summary judgment motion filed in blockbuster case",
            "story_body": "In a dramatic turn of events, the defendant has filed a motion for summary judgment that could potentially bring this high-profile celebrity lawsuit to an abrupt end. The motion argues that the plaintiff's case lacks merit and that no reasonable jury could find in their favor. Legal experts are calling this a 'make-or-break moment' in what has become one of the most watched court cases of the year.",
            "whats_next": "The court will schedule a hearing on this motion within 30-60 days. If granted, the case could be dismissed entirely. If denied, the case will proceed to trial as scheduled."
        }]
    }
}

mock_case_data = {
    'case_id': 'TEST123',
    'case_name': 'Celebrity vs. Tabloid Magazine',
    'case_url': 'https://example-court.com/case/123',
    'case_summary': 'A high-profile defamation lawsuit between a major celebrity and a tabloid magazine over allegedly false statements about the celebrity\'s personal life.'
}

mock_celebrities = "Famous Actor, Well-Known Director"

print("Testing clean email formatting (no colored backgrounds)...")
print("=" * 60)

# Generate the HTML
html_output = build_email_html(
    case_number="TEST123",
    case_name="Celebrity vs. Tabloid Magazine", 
    celebs=mock_celebrities,
    case_id="TEST123",
    case_summary=mock_case_data['case_summary'],
    events=mock_events,
    case_url=mock_case_data['case_url']
)

# Save to file for inspection
with open('test_clean_email_output.html', 'w', encoding='utf-8') as f:
    f.write(html_output)

print("✅ Clean email HTML generated successfully!")
print("📄 Output saved to: test_clean_email_output.html")
print("\nEmail preview (first 800 characters):")
print("-" * 40)
print(html_output[:800] + "..." if len(html_output) > 800 else html_output)
print("-" * 40)
print(f"Total email HTML length: {len(html_output)} characters")