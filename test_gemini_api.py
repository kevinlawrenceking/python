import requests
import json

print("Testing Gemini API...")
api_key = 'AIzaSyBFifwhmbta61-IPtgYCzEa7X_svoIzE5s'
url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}'

payload = {
    'contents': [
        {
            'role': 'user',
            'parts': [
                {'text': 'Hello, this is a test. Please respond with just "API working".'}
            ]
        }
    ],
    'generationConfig': {'temperature': 0.1, 'max_output_tokens': 10}
}

print(f"Making request to: {url[:80]}...")
try:
    response = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload), timeout=10)
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.text}')
    if response.status_code == 200:
        result = response.json()
        if 'candidates' in result:
            print("SUCCESS: API is working!")
            print(f"Generated text: {result['candidates'][0]['content']['parts'][0]['text']}")
        else:
            print("API responded but no candidates returned")
    else:
        print("API ERROR - Check the response above for details")
except Exception as e:
    print(f'Error: {e}')
    
print("Test completed.")
