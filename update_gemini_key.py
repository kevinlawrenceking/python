"""
Update Gemini API key in the database
"""
import pyodbc

print("Gemini API Key Updater")
print("="*70)
print("Get your API key from: https://aistudio.google.com/app/apikey")
print("="*70)

new_key = input("\nPaste your new API key here: ").strip()

if not new_key:
    print("❌ No key provided. Exiting.")
    exit(1)

if len(new_key) < 30:
    print(f"⚠ Warning: Key seems short ({len(new_key)} chars). Are you sure?")
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        exit(0)

# Update database
try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    cursor.execute("UPDATE docketwatch.dbo.utilities SET gemini_api = ?", (new_key,))
    conn.commit()
    
    print(f"\n✓ API key updated successfully!")
    print(f"  Key preview: {new_key[:15]}...{new_key[-5:]}")
    
    cursor.close()
    conn.close()
    
    print("\nNow test it with: python test_gemini_api.py")
    
except Exception as e:
    print(f"\n❌ Error updating database: {e}")
