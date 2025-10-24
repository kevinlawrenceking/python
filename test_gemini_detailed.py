"""
Detailed Gemini API Diagnostics

Tests various aspects of the API key and connection.
"""

import pyodbc
import google.generativeai as genai
import requests

# Get API key from database
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
row = cursor.fetchone()

if not row or not row[0]:
    print("❌ ERROR: No Gemini API key found in utilities table")
    exit(1)

api_key = row[0]
print(f"API Key: {api_key[:15]}...{api_key[-5:]}")
print(f"Key Length: {len(api_key)} characters")
print()

# Test 1: List models using REST API directly
print("="*70)
print("TEST 1: List Available Models (REST API)")
print("="*70)
try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Success! Found {len(data.get('models', []))} models")
        for model in data.get('models', [])[:5]:  # Show first 5
            print(f"  - {model.get('name', 'Unknown')}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.json())
except Exception as e:
    print(f"❌ Exception: {e}")

print()

# Test 2: Use SDK to list models
print("="*70)
print("TEST 2: List Models via SDK")
print("="*70)
try:
    genai.configure(api_key=api_key)
    models = list(genai.list_models())
    print(f"✓ Found {len(models)} models via SDK")
    
    for model in models[:5]:
        if 'generateContent' in model.supported_generation_methods:
            print(f"  ✓ {model.name} - supports generateContent")
except Exception as e:
    print(f"❌ Exception: {e}")

print()

# Test 3: Try different models
print("="*70)
print("TEST 3: Try Different Model Versions")
print("="*70)

models_to_test = [
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest', 
    'gemini-1.5-pro',
    'gemini-1.5-pro-latest',
    'gemini-pro',
]

for model_name in models_to_test:
    try:
        print(f"\nTrying {model_name}...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            "Reply with exactly: OK",
            generation_config=genai.GenerationConfig(
                temperature=0,
                max_output_tokens=10
            )
        )
        result = response.candidates[0].content.parts[0].text.strip()
        print(f"  ✓ SUCCESS: {result}")
        break  # If one works, we're good
    except Exception as e:
        error_str = str(e)
        if "404" in error_str:
            print(f"  ⚠ Model not found")
        elif "403" in error_str or "blocked" in error_str.lower():
            print(f"  ❌ BLOCKED: {error_str[:100]}")
        elif "429" in error_str or "quota" in error_str.lower():
            print(f"  ⚠ Quota exceeded")
        else:
            print(f"  ❌ Error: {error_str[:100]}")

print()
print("="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)

cursor.close()
conn.close()
