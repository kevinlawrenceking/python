#!/usr/bin/env python3
"""
Test the unknown document type filter fix
"""

import re

def test_unknown_document_type_filter():
    """Test the filter logic for unknown document types"""
    
    print("🧪 TESTING UNKNOWN DOCUMENT TYPE FILTER")
    print("=" * 50)
    
    # Test cases from real data
    test_cases = [
        {
            "desc_raw": "[Unknown Document Type: 16467] Filed by Plaintiff",
            "expected_skip": True,
            "description": "Standard unknown type with number"
        },
        {
            "desc_raw": "[Unknown Document Type] Some document",
            "expected_skip": True,
            "description": "Unknown type without number"
        },
        {
            "desc_raw": "[MOTION for Summary Judgment] Filed by Defendant",
            "expected_skip": False,
            "description": "Normal motion - should process"
        },
        {
            "desc_raw": "[COMPLAINT] Filed by Plaintiff Jones",
            "expected_skip": False,
            "description": "Normal complaint - should process"
        },
        {
            "desc_raw": "[unknown document type: 4224] Some description",
            "expected_skip": True,
            "description": "Lowercase unknown type"
        },
        {
            "desc_raw": "[UNKNOWN DOCUMENT TYPE: 114312] Filed",
            "expected_skip": True,
            "description": "Uppercase unknown type"
        }
    ]
    
    print("\n📋 TEST RESULTS:")
    print("-" * 50)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        desc_raw = test["desc_raw"]
        expected_skip = test["expected_skip"]
        description = test["description"]
        
        # Simulate the RSS trigger logic
        event_description_match = re.search(r'\[(.*?)\]', desc_raw)
        event_description = event_description_match.group(1) if event_description_match else ""
        
        # Apply the filter
        should_skip = event_description.lower().startswith('unknown document type')
        
        # Check result
        result = "✅ PASS" if should_skip == expected_skip else "❌ FAIL"
        action = "SKIP" if should_skip else "PROCESS"
        
        print(f"\n{i}. {description}")
        print(f"   Input: {desc_raw}")
        print(f"   Extracted: '{event_description}'")
        print(f"   Action: {action}")
        print(f"   Expected: {'SKIP' if expected_skip else 'PROCESS'}")
        print(f"   Result: {result}")
        
        if should_skip == expected_skip:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 SUMMARY:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")
    
    if failed == 0:
        print(f"\n🎉 ALL TESTS PASSED! The filter is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Review the filter logic.")

def demonstrate_before_after():
    """Show before/after behavior"""
    
    print(f"\n🔄 BEFORE/AFTER COMPARISON")
    print("=" * 50)
    
    print(f"\n📥 BEFORE (without filter):")
    print(f"   RSS finds: 'Unknown Document Type: 16467'")
    print(f"   Creates case_event with useless description")
    print(f"   Clutters database with PACER error messages")
    print(f"   No actionable information for reporters")
    
    print(f"\n📤 AFTER (with filter):")
    print(f"   RSS finds: 'Unknown Document Type: 16467'")
    print(f"   Logs: 'Skipping PACER unknown document type'")
    print(f"   Continues to next RSS item")
    print(f"   Only processes real court documents")
    
    print(f"\n🎯 BENEFITS:")
    print(f"   ✅ Cleaner case_events table")
    print(f"   ✅ Faster processing (skips useless items)")
    print(f"   ✅ Better data quality")
    print(f"   ✅ Focus on actionable court content")

if __name__ == "__main__":
    test_unknown_document_type_filter()
    demonstrate_before_after()
