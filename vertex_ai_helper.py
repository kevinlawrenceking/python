"""
Vertex AI Helper for Gemini API using Service Account Authentication
This replaces the simple API key approach with enterprise-grade authentication.
"""

import os
import json
import logging
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, SafetySetting, HarmCategory, HarmBlockThreshold
from typing import Optional, Dict, Any

PROJECT_ID = "docketwatch"  # Your GCP project ID
REGION = "us-central1"
DEFAULT_MODEL = "gemini-2.0-flash-exp"  # Default model, can be overridden

# Use absolute path to service account file (same directory as this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(SCRIPT_DIR, "docketwatch-service-account.json")

# Initialize Vertex AI once at module load
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = SERVICE_ACCOUNT_FILE
vertexai.init(project=PROJECT_ID, location=REGION)

# Safety settings for legal documents
SAFETY_SETTINGS = [
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
]

def get_vertex_ai_token():
    """Get authentication token from service account."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return creds.token

def generate_content_vertex(prompt: str, temperature: float = 0.5, max_tokens: int = 2048) -> str:
    """
    Generate content using Vertex AI Gemini API.
    
    Args:
        prompt: The text prompt to send to Gemini
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens to generate
        
    Returns:
        Generated text response
        
    Raises:
        Exception if API call fails
    """
    token = get_vertex_ai_token()
    
    url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{MODEL}:generateContent"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    data = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generation_config": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "response_modalities": ["TEXT"]  # Disable thinking mode to get more output tokens
        },
        "safety_settings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code != 200:
        raise Exception(f"Vertex AI API error {response.status_code}: {response.text}")
    
    result = response.json()
    
    # Extract text from response
    if "candidates" in result and len(result["candidates"]) > 0:
        candidate = result["candidates"][0]
        
        # Check finish reason
        finish_reason = candidate.get("finishReason", "UNKNOWN")
        if finish_reason not in ["STOP", "MAX_TOKENS"]:
            raise Exception(f"Generation failed with finish reason: {finish_reason}")
        
        if "content" in candidate and "parts" in candidate["content"]:
            parts = candidate["content"]["parts"]
            if len(parts) > 0 and "text" in parts[0]:
                return parts[0]["text"].strip()
        
        # If no parts but finished successfully, might be empty response
        if finish_reason == "STOP":
            return ""
    
    raise Exception(f"No text content in response: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    # Test the Vertex AI connection
    print("Testing Vertex AI connection...")
    try:
        result = generate_content_vertex("Say OK", temperature=0, max_tokens=100)
        print(f"✓ SUCCESS: {result}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
