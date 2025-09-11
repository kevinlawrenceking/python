"""
Test Gemini API connectivity and permissions
"""
import pyodbc
import requests
import json

def test_gemini_api():
    try:
        # Get API key from database
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        api_key = row[0] if row and row[0] else None
        cursor.close()
        conn.close()
        
        if not api_key:
            print("❌ No Gemini API key found in database")
            return
            
        print(f"✓ Found API key: {api_key[:20]}...{api_key[-10:]}")
        
        # Test simple API call with Flash model (might have different permissions)
        models_to_test = [
            "gemini-1.5-flash", 
            "gemini-1.5-pro",
            "gemini-pro"
        ]
        
        for model in models_to_test:
            print(f"\n🔄 Testing {model}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Say hello"}]}],
                "generationConfig": {"temperature": 0.1, "max_output_tokens": 10}
            }
            
            response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
            
            print(f"📊 {model} Response status: {response.status_code}")
            result = response.json()
            
            if response.status_code == 200:
                if result.get("candidates"):
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ {model} working! Response: {text}")
                    break  # Found working model
                else:
                    print(f"⚠️ {model} responded but no content: {json.dumps(result, indent=2)}")
            else:
                print(f"❌ {model} Error: {json.dumps(result, indent=2)}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_gemini_api()
