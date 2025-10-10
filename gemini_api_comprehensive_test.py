#!/usr/bin/env python3
"""
Comprehensive Gemini API Tester - Check available models and API restrictions
Tests both REST API and Python SDK approaches
"""

import pyodbc
import google.generativeai as genai
import requests
import json
import sys
from datetime import datetime

def get_gemini_key(cursor):
    """Get Gemini API key from database"""
    try:
        cursor.execute("SELECT gemini_api_damz as gemini_api FROM docketwatch.dbo.utilities")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    except Exception as e:
        print(f"ERROR getting API key from database: {e}")
        return None

def test_rest_api_models(api_key):
    """Test models via REST API"""
    print("=== TESTING REST API MODELS ===")
    
    # List models via REST API
    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            print(f"✓ Found {len(models)} models via REST API")
            
            generate_models = []
            for model in models:
                name = model.get('name', 'Unknown')
                methods = model.get('supportedGenerationMethods', [])
                
                if 'generateContent' in methods:
                    generate_models.append(name)
                    print(f"  ✓ {name} - supports generateContent")
                else:
                    print(f"  ✗ {name} - no generateContent support")
            
            return generate_models
        else:
            print(f"✗ REST API failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"✗ REST API error: {e}")
        return []

def test_sdk_models(api_key):
    """Test models via Python SDK"""
    print("\n=== TESTING PYTHON SDK MODELS ===")
    
    try:
        genai.configure(api_key=api_key)
        models = list(genai.list_models())
        
        print(f"✓ Found {len(models)} models via SDK")
        
        generate_models = []
        for model in models:
            name = model.name
            methods = model.supported_generation_methods
            
            if 'generateContent' in methods:
                generate_models.append(name)
                print(f"  ✓ {name} - supports generateContent")
            else:
                print(f"  ✗ {name} - no generateContent support")
        
        return generate_models
        
    except Exception as e:
        print(f"✗ SDK error: {e}")
        return []

def test_specific_model_rest(api_key, model_name):
    """Test specific model via REST API"""
    try:
        # Extract model name without 'models/' prefix for URL
        clean_name = model_name.replace('models/', '')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{clean_name}:generateContent?key={api_key}'
        
        payload = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [{'text': 'Test message. Reply with "OK".'}]
                }
            ],
            'generationConfig': {'temperature': 0.0, 'max_output_tokens': 10}
        }
        
        response = requests.post(
            url, 
            headers={'Content-Type': 'application/json'}, 
            data=json.dumps(payload), 
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                text = result['candidates'][0]['content']['parts'][0]['text']
                print(f"  ✓ REST: {model_name} - Response: {text.strip()}")
                return True
            else:
                print(f"  ✗ REST: {model_name} - No candidates in response")
                return False
        else:
            print(f"  ✗ REST: {model_name} - HTTP {response.status_code}: {response.text[:100]}")
            return False
            
    except Exception as e:
        print(f"  ✗ REST: {model_name} - Error: {e}")
        return False

def test_specific_model_sdk(api_key, model_name):
    """Test specific model via Python SDK"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        response = model.generate_content(
            "Test message. Reply with 'OK'.",
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 10
            }
        )
        
        text = response.text.strip()
        print(f"  ✓ SDK:  {model_name} - Response: {text}")
        return True
        
    except Exception as e:
        print(f"  ✗ SDK:  {model_name} - Error: {e}")
        return False

def test_vision_model(api_key, model_name):
    """Test vision capability"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        # Create minimal test image
        import base64
        import tempfile
        import os
        
        # 1x1 red pixel PNG
        png_data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_file.write(png_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload and test
            image_file = genai.upload_file(path=tmp_path)
            
            response = model.generate_content(
                ["What color is this image?", image_file],
                generation_config={"temperature": 0.0, "max_output_tokens": 50}
            )
            
            # Cleanup
            genai.delete_file(image_file.name)
            os.unlink(tmp_path)
            
            text = response.text.strip()
            print(f"  ✓ VISION: {model_name} - Response: {text}")
            return True
            
        except Exception as vision_error:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise vision_error
            
    except Exception as e:
        print(f"  ✗ VISION: {model_name} - Error: {e}")
        return False

def comprehensive_model_test(api_key, models_to_test):
    """Test each model comprehensively"""
    print(f"\n=== COMPREHENSIVE MODEL TESTING ===")
    
    results = {
        'rest_working': [],
        'sdk_working': [],
        'vision_working': []
    }
    
    for model_name in models_to_test:
        print(f"\nTesting: {model_name}")
        
        # Test REST API
        if test_specific_model_rest(api_key, model_name):
            results['rest_working'].append(model_name)
        
        # Test SDK
        if test_specific_model_sdk(api_key, model_name):
            results['sdk_working'].append(model_name)
        
        # Test vision (for capable models)
        if any(x in model_name.lower() for x in ['vision', '1.5', 'image', 'flash-exp']):
            if test_vision_model(api_key, model_name):
                results['vision_working'].append(model_name)
    
    return results

def generate_final_report(results):
    """Generate final recommendations"""
    print(f"\n{'='*60}")
    print("FINAL REPORT & RECOMMENDATIONS")
    print(f"{'='*60}")
    
    print(f"\nWORKING MODELS (REST API): {len(results['rest_working'])}")
    for model in results['rest_working']:
        print(f"  ✓ {model}")
    
    print(f"\nWORKING MODELS (Python SDK): {len(results['sdk_working'])}")
    for model in results['sdk_working']:
        print(f"  ✓ {model}")
    
    print(f"\nVISION-CAPABLE MODELS: {len(results['vision_working'])}")
    for model in results['vision_working']:
        print(f"  👁️ {model}")
    
    print(f"\nRECOMMENDATIONS FOR YOUR SCRIPT:")
    if results['vision_working']:
        if 'models/gemini-1.5-flash' in results['vision_working']:
            print(f"  🎯 BEST CHOICE: gemini-1.5-flash (fast, cost-effective, vision)")
            print(f"     Update your script: GEMINI_MODEL = 'gemini-1.5-flash'")
        elif 'models/gemini-1.5-pro' in results['vision_working']:
            print(f"  🎯 BEST CHOICE: gemini-1.5-pro (most capable, vision)")
            print(f"     Update your script: GEMINI_MODEL = 'gemini-1.5-pro'")
        else:
            print(f"  🎯 USE: {results['vision_working'][0]} (available vision model)")
    else:
        print(f"  ❌ NO VISION MODELS AVAILABLE")
        print(f"     Your image processing script will not work!")
        print(f"     Enable gemini-1.5-flash or gemini-1.5-pro in Google AI Studio")
    
    if not results['sdk_working']:
        print(f"\n  ⚠️  PYTHON SDK NOT WORKING")
        print(f"     Check API key restrictions in Google AI Studio")
        print(f"     Ensure 'Generative Language API' is enabled")

def main():
    print("COMPREHENSIVE GEMINI API TESTER")
    print("=" * 60)
    print(f"Test started: {datetime.now()}")
    
    # Get API key from database
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        api_key = get_gemini_key(cursor)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"ERROR connecting to database: {e}")
        return
    
    if not api_key:
        print("ERROR: No Gemini API key found in database")
        return
    
    print(f"API Key: {api_key[:15]}...{'*' * (len(api_key) - 15)}")
    
    # Test both REST and SDK model discovery
    rest_models = test_rest_api_models(api_key)
    sdk_models = test_sdk_models(api_key)
    
    # Get unique models from both sources
    all_models = list(set(rest_models + sdk_models))
    
    if not all_models:
        print("\n❌ NO MODELS FOUND - Check your API restrictions!")
        return
    
    print(f"\nUnique models found: {len(all_models)}")
    
    # Test each model comprehensively
    results = comprehensive_model_test(api_key, all_models)
    
    # Generate final report
    generate_final_report(results)
    
    print(f"\nTest completed: {datetime.now()}")

if __name__ == "__main__":
    main()