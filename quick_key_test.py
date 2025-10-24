import google.generativeai as genai
import sys

key = "AIzaSyBhXn57UoX0DfLS90uTpNb1xhdlYFONqf0"

print(f"Testing key: {key[:15]}...{key[-5:]}")
sys.stdout.flush()

try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content('Say OK')
    print(f"✓ SUCCESS: {response.text}")
    sys.stdout.flush()
except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.stdout.flush()
