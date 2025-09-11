"""
Test the improved Gemini API with retry logic
"""
import requests
import json
import time
import pyodbc

def get_api_key():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    api_key = row[0] if row and row[0] else None
    cursor.close()
    conn.close()
    return api_key

def test_gemini_with_retry():
    api_key = get_api_key()
    if not api_key:
        print("❌ No API key found")
        return
    
    print(f"✓ Found API key: {api_key[:20]}...{api_key[-10:]}")
    
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro", 
        "gemini-pro"
    ]
    
    for model_name in models_to_try:
        print(f"\n🔄 Testing {model_name}...")
        
        for attempt in range(2):  # Just 2 attempts for testing
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({
                        "contents": [{"role": "user", "parts": [{"text": "Say hello in 5 words"}]}],
                        "generationConfig": {"temperature": 0.1, "max_output_tokens": 20}
                    }),
                    timeout=10  # 10 second timeout
                )
                
                print(f"📊 {model_name} status: {response.status_code}")
                result = response.json()
                
                if response.status_code == 200 and result.get("candidates"):
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ {model_name} SUCCESS: {text}")
                    return  # Success, stop testing
                elif response.status_code == 503:
                    print(f"⏳ {model_name} overloaded, waiting 5s...")
                    time.sleep(5)
                else:
                    print(f"❌ {model_name} error: {json.dumps(result, indent=2)}")
                    break  # Try next model
                    
            except Exception as e:
                print(f"💥 {model_name} exception: {e}")
                break
    
    print("❌ All models failed")

if __name__ == "__main__":
    test_gemini_with_retry()
