#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Import the build_email_html function
from docketwatch_case_events_alert_plus2 import build_email_html
from datetime import datetime

# Mock data with multiple events to test indentation
mock_events = {
    "12345": {
        "event_description": "Motion for Summary Judgment Filed",
        "event_date": datetime(2024, 9, 23),
        "created_at": datetime(2024, 9, 23, 14, 30),
        "documents": [{
            "pdf_title": "Motion for Summary Judgment",
            "event_summary": "Defendant's motion for summary judgment argues that there are no genuine disputes of material fact.",
            "newsworthiness": "YES",
            "newsworthiness_reason": "This motion could potentially end the high-profile case if granted by the court.",
            "story_headline": "BOMBSHELL LEGAL MOVE: Defendant Files Motion That Could End Celebrity Lawsuit",
            "story_sub_head": "High-stakes summary judgment motion filed in blockbuster case",
            "story_body": "In a dramatic turn of events, the defendant has filed a motion for summary judgment that could potentially bring this high-profile celebrity lawsuit to an abrupt end.",
            "whats_next": "The court will schedule a hearing on this motion within 30-60 days."
        }]
    },
    "12346": {
        "event_description": "Letter - Discovery Response",
        "event_date": datetime(2024, 9, 22),
        "created_at": datetime(2024, 9, 23, 9, 16),
        "documents": [{
            "pdf_title": "Letter",
            "event_summary": "Attorneys for defendants responded to a court order regarding the scope of discovery in the sexual assault lawsuit.",
            "newsworthiness": "YES",
            "newsworthiness_reason": "This filing reveals legal strategy to severely limit discovery in a sexual assault case, references vast amounts of evidence seized in separate federal criminal case.",
            "story_headline": "",
            "story_sub_head": "", 
            "story_body": "",
            "whats_next": "Court must now rule on the scope of discovery before proceeding with depositions."
        }]
    }
}

mock_case_data = {
    'case_id': 'TEST123',
    'case_name': 'Doe v. Combs et al',
    'case_url': 'https://example-court.com/case/123',
    'case_summary': 'A high-profile sexual assault lawsuit with multiple defendants including Sean Combs.'
}

mock_celebrities = "Sean Combs"

print("Testing multi-event email formatting with proper indentation...")
print("=" * 60)

# Generate the HTML
html_output = build_email_html(
    case_number="1:23-cv-10628-JGLC",
    case_name="Doe v. Combs et al", 
    celebs=mock_celebrities,
    case_id="TEST123",
    case_summary=mock_case_data['case_summary'],
    events=mock_events,
    case_url=mock_case_data['case_url']
)

# Save to file for inspection
with open('test_multi_event_output.html', 'w', encoding='utf-8') as f:
    f.write(html_output)

print("✅ Multi-event email HTML generated successfully!")
print("📄 Output saved to: test_multi_event_output.html")
print("\nEmail preview (first 1000 characters):")
print("-" * 40)
print(html_output[:1000] + "..." if len(html_output) > 1000 else html_output)
print("-" * 40)
print(f"Total email HTML length: {len(html_output)} characters")