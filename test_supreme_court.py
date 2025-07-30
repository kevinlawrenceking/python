# test_supreme_court.py
# Simple test of Supreme Court monitoring functionality

import json
import requests
import os
from datetime import datetime

def test_fetch_data():
    """Test fetching Supreme Court data"""
    case_number = "24-1073"
    url = f"https://www.supremecourt.gov/RSS/Cases/JSON/{case_number}.json"
    
    print(f"Fetching data from: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ Successfully fetched data")
        print(f"Case: {data.get('PetitionerTitle', 'Unknown')} v. {data.get('RespondentTitle', 'Unknown')}")
        print(f"Number of proceedings: {len(data.get('ProceedingsandOrder', []))}")
        
        # Show the latest proceeding
        proceedings = data.get('ProceedingsandOrder', [])
        if proceedings:
            latest = proceedings[-1]
            print(f"Latest proceeding: {latest['Date']} - {latest['Text'][:100]}...")
        
        # Save to test file
        test_file = "test_supreme_court_data.json"
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Data saved to {test_file}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Supreme Court data fetching...")
    test_fetch_data()
