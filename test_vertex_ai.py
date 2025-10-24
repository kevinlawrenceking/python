"""
Test Vertex AI access with service account
"""
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

PROJECT_ID = "fox-sharedservices-sandbox1"
MODEL = "gemini-2.5-flash"
REGION = "us-central1"

# Load credentials
print("Loading service account credentials...")
creds = service_account.Credentials.from_service_account_file(
    "fox-sharedservices-sandbox1-e6bd1d26f441.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
creds.refresh(Request())
token = creds.token
print(f"✓ Token obtained: {token[:20]}...")

# Prepare request
url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{MODEL}:generateContent"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

data = {
    "contents": [
        {
            "role": "user",
            "parts": [{"text": "Say OK"}]
        }
    ]
}

print("\nSending request to Vertex AI...")
response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    result = response.json()
    if 'candidates' in result and result['candidates']:
        text = result['candidates'][0]['content']['parts'][0]['text']
        print(f"✓ SUCCESS: {text}")
    else:
        print("Response:")
        print(json.dumps(result, indent=2))
else:
    print(f"❌ ERROR {response.status_code}:")
    print(json.dumps(response.json(), indent=2))
