import pyodbc

# DB Connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

def insert_case(case_number, case_name, owner, status, fk_tool):
    cursor.execute("""
        INSERT INTO cases (
            case_number, case_name, owner, status, fk_tool
        ) VALUES (
            ?, ?, ?, ?, ?
        );
    """, case_number, case_name, owner, status, fk_tool)

    cursor.execute("SELECT SCOPE_IDENTITY()")
    return cursor.fetchone()[0]

def process_cursor():
    cursor.execute("""
        SELECT  
            f.case_number,
            f.case_title AS case_name,
            u.username AS owner,
            'Tracked' AS status,
            0 AS fk_case,
            12 AS fk_tool,
            f.case_number AS case_number,
            f.case_title AS case_name,
            1 AS is_tracked,
            f.map_id
        FROM docketwatch.dbo.followed_cases f
        INNER JOIN docketwatch.dbo.users u ON u.email = f.email_address
        WHERE NOT EXISTS (
            SELECT 1 
            FROM docketwatch.dbo.tool_cases tc 
            WHERE tc.case_number = f.case_number
        )
        AND f.date_added > '2019-12-31'
    """)ca

    rows = cursor.fetchall()
    print(f"Found {len(rows)} followed cases to process...")

    for row in rows:
        print(f"Processing case: {row.case_number}")

        fk_case = insert_case(row.case_number, row.case_name, row.owner, row.status, row.fk_tool)
        if not fk_case:
            print(f"⚠️  Failed to insert case: {row.case_number}")
            continue

    conn.commit()
    print("All done.")
