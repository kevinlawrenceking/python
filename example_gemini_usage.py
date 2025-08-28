"""
Example script showing how to use Gemini logging functions from scraper_base.py

This demonstrates how any script can easily add Gemini API logging by importing 
the functions from scraper_base.py
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper_base import (
    get_db_cursor, 
    gemini_api_call_with_logging, 
    get_gemini_usage_stats,
    log_message
)

def example_gemini_analysis():
    """Example function showing how to use Gemini with logging"""
    
    # Get database connection
    conn, cursor = get_db_cursor()
    script_name = os.path.basename(__file__)
    
    try:
        # Show current usage stats
        stats = get_gemini_usage_stats(cursor, script_name, days=7)
        if stats:
            print(f"Recent usage for {script_name}:")
            print(f"  Total calls: {stats['total_calls']}")
            print(f"  Success rate: {stats['successful_calls']}/{stats['total_calls']}")
            print(f"  Total tokens: {stats['total_tokens']:,}")
            print(f"  Estimated cost: ${stats['estimated_cost']:.6f}")
        
        # Example: Analyze some text with Gemini
        sample_prompt = """
        You are a legal document classifier. Classify the following text as one of:
        - Motion
        - Order
        - Filing
        - Notice
        - Other
        
        Text: "MOTION FOR SUMMARY JUDGMENT
        
        Plaintiff hereby moves this Court for summary judgment on all claims..."
        
        Response format: Classification: [type]
        """
        
        # Make Gemini call with automatic logging
        response_text, success = gemini_api_call_with_logging(
            cursor=cursor,
            script_name=script_name,
            model_name="gemini-2.5-flash",
            prompt=sample_prompt,
            fk_asset=None,  # No specific asset for this example
            temperature=0.1,
            max_tokens=50
        )
        
        if success:
            print(f"\nGemini Response: {response_text}")
            log_message(cursor, None, "INFO", f"Successfully classified document: {response_text}")
        else:
            print("Gemini call failed - check logs")
            log_message(cursor, None, "ERROR", "Document classification failed")
        
        # Show updated usage stats
        updated_stats = get_gemini_usage_stats(cursor, script_name, days=1)
        if updated_stats:
            print(f"\nToday's usage after this call:")
            print(f"  Calls today: {updated_stats['total_calls']}")
            print(f"  Tokens today: {updated_stats['total_tokens']:,}")
            print(f"  Cost today: ${updated_stats['estimated_cost']:.6f}")
        
    except Exception as e:
        print(f"Error: {e}")
        log_message(cursor, None, "ERROR", f"Script error: {e}")
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    example_gemini_analysis()
