import pyodbc

# Quick script to check the database table structure
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

print("Checking damz_test table structure...")

# Get all columns
cursor.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'damz_test' AND TABLE_SCHEMA = 'dbo'
    ORDER BY ORDINAL_POSITION
""")

columns = cursor.fetchall()
print(f"Found {len(columns)} columns:")

for col in columns:
    print(f"  {col[0]} ({col[1]}) - Nullable: {col[2]}")

# Check for our specific columns
target_columns = ['headline_type_v2', 'headline_v2']
existing_columns = [col[0] for col in columns]

for target in target_columns:
    if target in existing_columns:
        print(f"✓ Column '{target}' exists")
    else:
        print(f"✗ Column '{target}' MISSING")

# Check a sample record
cursor.execute("SELECT TOP 1 fk_asset FROM damz_test")
sample = cursor.fetchone()
if sample:
    print(f"\nSample record: {sample[0]}")
    
    # Try to select the specific columns we need
    try:
        cursor.execute(f"SELECT headline_type_v2, headline_v2 FROM damz_test WHERE fk_asset = ?", (sample[0],))
        result = cursor.fetchone()
        print(f"Current values: Type='{result[0]}', Headline='{result[1]}'")
    except Exception as e:
        print(f"Error accessing target columns: {e}")

cursor.close()
conn.close()
