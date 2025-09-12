#!/usr/bin/env python3
"""
Case Event Pipeline Button - Command Options

This shows the different commands you could use for a button that runs
the pipeline on a specific case event.
"""

def get_pipeline_commands(case_id, event_no, court_code, case_event_id):
    """
    Return the different command options for running the pipeline on a case event.
    
    Args:
        case_id: The case ID (e.g., 107769)
        event_no: The event number (e.g., 138)
        court_code: The court code (e.g., "flsd")
        case_event_id: The case event GUID (e.g., "7CD5BD5C-7048-49A3-A495-FAE57A00EB42")
    
    Returns:
        dict: Commands for different purposes
    """
    
    commands = {
        # RECOMMENDED: Full pipeline with enhanced PDF handling
        "full_pipeline_enhanced": {
            "command": f"python U:\\docketwatch\\python\\single_case_event_pipeline.py {case_id} {event_no} {court_code}",
            "description": "Runs complete pipeline including PACER scrape, PDF download (with enhanced error handling), OCR, and AI summarization",
            "best_for": "General use - handles everything including 'Cannot redisplay' errors"
        },
        
        # Modern approach using the modernized processor
        "modernized_processor": {
            "command": f"python U:\\docketwatch\\python\\modernized_pacer_processor.py {case_event_id}",
            "description": "Uses modern Python patterns with workflow orchestration",
            "best_for": "Modern architecture, better error handling and logging"
        },
        
        # Enhanced PDF downloader only (for PDF issues)
        "enhanced_pdf_only": {
            "command": f"python U:\\docketwatch\\python\\lightweight_enhanced_downloader.py {case_event_id}",
            "description": "Only downloads PDFs using lightweight enhanced error handling for PACER restrictions",
            "best_for": "When you only need PDF download with redisplay error handling"
        },
        
        # Original PDF downloader only
        "original_pdf_only": {
            "command": f"python U:\\docketwatch\\python\\extract_pacer_pdf_file.py {case_event_id}",
            "description": "Only downloads PDFs using original method",
            "best_for": "Simple PDF download without enhanced error handling"
        },
        
        # Process new event function directly (internal)
        "process_new_event": {
            "command": f"python -c \"from docketwatch_rss_trigger import process_new_event; process_new_event({case_id}, {event_no}, '{court_code}')\"",
            "description": "Calls the process_new_event function directly",
            "best_for": "Internal use or when you want to call the function programmatically"
        }
    }
    
    return commands

def recommend_command_for_button():
    """Recommend the best command for a case event button"""
    
    print("🔘 CASE EVENT PIPELINE BUTTON - COMMAND RECOMMENDATIONS")
    print("=" * 65)
    
    print("\n🎯 RECOMMENDED FOR MOST CASES:")
    print("Command: python single_case_event_pipeline.py {case_id} {event_no} {court_code}")
    print("Why: Complete pipeline with enhanced PDF handling built-in")
    
    print("\n📋 FOR YOUR PETE V. COOPER EXAMPLE:")
    print("Command: python single_case_event_pipeline.py 107769 138 flsd")
    print("What it does:")
    print("  ✅ PACER scraping")
    print("  ✅ Document sync") 
    print("  ✅ Enhanced PDF download (handles 'Cannot redisplay')")
    print("  ✅ OCR processing")
    print("  ✅ AI summarization")
    print("  ✅ Status updates")
    
    print("\n🔧 ALTERNATIVE OPTIONS:")
    
    print("\n1️⃣ Modern Architecture:")
    print("   Command: python modernized_pacer_processor.py {case_event_id}")
    print("   Best for: Better logging, modern code patterns")
    
    print("\n2️⃣ PDF Issues Only:")
    print("   Command: python enhanced_pacer_pdf_downloader.py {case_event_id}")
    print("   Best for: When you only need to fix PDF download issues")
    
    print("\n💡 IMPLEMENTATION SUGGESTIONS:")
    print("=" * 30)
    
    print("\nFor a web button:")
    print("• Use single_case_event_pipeline.py as the backend command")
    print("• Pass case_id, event_no, court_code as parameters")
    print("• Show progress/status to user")
    print("• Handle timeouts (pipeline can take 2-5 minutes)")
    
    print("\nFor a desktop app button:")
    print("• Same command but run in background thread")
    print("• Show real-time log output to user")
    print("• Allow cancellation if needed")
    
    print("\nParameters needed:")
    print("• case_id (from cases table)")
    print("• event_no (from case_events table)")
    print("• court_code (from case_events table)")
    
    print("\n🚀 READY-TO-USE COMMAND:")
    print("python single_case_event_pipeline.py {case_id} {event_no} {court_code}")

if __name__ == "__main__":
    # Example with Pete v. Cooper case
    case_id = 107769
    event_no = 138
    court_code = "flsd"
    case_event_id = "7CD5BD5C-7048-49A3-A495-FAE57A00EB42"
    
    print("📋 CASE EVENT PIPELINE COMMANDS")
    print("=" * 40)
    print(f"Example Case: Pete v. Cooper")
    print(f"Case ID: {case_id}")
    print(f"Event No: {event_no}")
    print(f"Court: {court_code}")
    print(f"Case Event ID: {case_event_id}")
    
    commands = get_pipeline_commands(case_id, event_no, court_code, case_event_id)
    
    print(f"\n🎯 AVAILABLE COMMANDS:")
    print("-" * 25)
    
    for key, cmd_info in commands.items():
        print(f"\n• {cmd_info['description']}")
        print(f"  Command: {cmd_info['command']}")
        print(f"  Best for: {cmd_info['best_for']}")
    
    print("\n" + "="*60)
    recommend_command_for_button()
