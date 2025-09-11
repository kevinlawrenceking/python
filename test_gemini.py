import requests
AIzaSyDzgx4_USN5_Fg79Y3tM8C3Sff1Ux_HsD8
API_KEY = "AIzaSyBZAdSnlK62d7LG2c1RCRuuGXQ4pV3j43o"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

def test_gemini():
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": "Quick test: reply with 'Gemini API key works!'"}]}
        ]
    }

    response = requests.post(URL, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            print("Response:", text)
        except Exception as e:
            print("Unexpected response structure:", result)
    else:
        print("Error:", response.status_code, response.text)

if __name__ == "__main__":
    test_gemini()
