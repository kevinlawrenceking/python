"""
Check the database schema for the cases table to determine actual column limits
"""

import pyodbc

try:
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    print("Checking column limits for cases table...")
    print("=" * 50)
    
    # Query to get column information
    cursor.execute("""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            CHARACTER_MAXIMUM_LENGTH,
            IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'cases' 
        AND TABLE_SCHEMA = 'dbo'
        ORDER BY ORDINAL_POSITION
    """)
    
    columns = cursor.fetchall()
    
    for col in columns:
        column_name, data_type, max_length, nullable = col
        max_length_str = str(max_length) if max_length else "N/A"
        print(f"{column_name:20} | {data_type:15} | Max Length: {max_length_str:10} | Nullable: {nullable}")
    
    print("\n" + "=" * 50)
    print("Key fields to check:")
    print("- courtCaseNumber: Look for max length")
    print("- case_name: Look for max length") 
    print("- case_type: Look for max length")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error checking schema: {e}")
