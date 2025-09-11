import pyodbc

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    # Check PACER tool configuration
    print("=== PACER Tool Configuration ===")
    cursor.execute("""
        SELECT username, pass, login_url
        FROM docketwatch.dbo.tools 
        WHERE id = 2
    """)
    row = cursor.fetchone()
    if row:
        print(f"Login URL: {row.login_url}")
        print(f"Username: {row.username}")
        password_value = getattr(row, 'pass', None)
        if password_value:
            password_masked = '*' * len(password_value)
        else:
            password_masked = 'None'
        print(f"Password: {password_masked}")
    else:
        print("No PACER tool found with ID 2")
    
    # Check Gemini API key
    print("\n=== Gemini API Configuration ===")
    cursor.execute("SELECT gemini_api FROM docketwatch.dbo.utilities")
    row = cursor.fetchone()
    if row and row[0]:
        print(f"Gemini API Key: {row[0][:20]}...{row[0][-10:]}")
    else:
        print("No Gemini API key found")
        
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Database error: {e}")
