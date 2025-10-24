"""Quick test of new API key"""
import google.generativeai as genai

api_key = "AIzaSyBr4o5QXg1BcDOXbGYdqwWnOqAU5jiQrGc"
print(f"Testing key: {api_key[:15]}...{api_key[-5:]}")

genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Say OK")
    print(f"✓ SUCCESS: {response.text}")
    print("\nKey is valid! Now updating database...")
    
    import pyodbc
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    cursor.execute("UPDATE docketwatch.dbo.utilities SET gemini_api = ?", (api_key,))
    conn.commit()
    cursor.close()
    conn.close()
    print("✓ Database updated!")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
