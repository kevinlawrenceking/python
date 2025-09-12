#!/usr/bin/env python3
"""
Quick Test for Pete v. Cooper Case Event
Test the enhanced PDF downloader on the specific case from your log.
"""

print("🎯 TESTING ENHANCED PDF DOWNLOADER")
print("Case: Pete v. Cooper - Event 138")
print("=" * 50)

print("\n📋 CASE EVENT FROM YOUR LOG:")
print("Case Event ID: 7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
print("Case ID: 107769") 
print("Event No: 138")
print("Court: FLSD")
print("Case Name: Pete v. Cooper")

print("\n🧪 TESTING OPTIONS:")
print("-" * 30)

print("\n1️⃣  TEST ENHANCED DOWNLOADER DIRECTLY:")
print("   Command: python enhanced_pacer_pdf_downloader.py 7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
print("   This will test the enhanced downloader specifically")

print("\n2️⃣  TEST VIA SINGLE EVENT PIPELINE:")
print("   Command: python single_case_event_pipeline.py 107769 138 flsd") 
print("   This will run the full pipeline (including enhanced downloader)")

print("\n3️⃣  TEST WITH DETAILED OUTPUT:")
print("   Command: python test_single_case_event_pdf.py 7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
print("   This will show detailed before/after analysis")

print("\n🔍 WHAT TO WATCH FOR:")
print("✅ 'Enhanced PACER PDF download' - Using new downloader")
print("⚠️  'Redisplay error detected' - Found the problem")  
print("🔄 'Creating fresh session' - Applying solution")
print("✅ 'Successfully downloaded via alternative method' - Fixed!")

print("\n📝 EXPECTED OUTCOME:")
print("The enhanced downloader should:")
print("• Detect any 'Cannot redisplay' errors")
print("• Create fresh browser sessions")
print("• Successfully download the PDF that previously failed")
print("• Update the document status to 'downloaded'")

print("\n🚀 TRY THIS FIRST:")
print("python test_single_case_event_pdf.py 7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
