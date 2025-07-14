from generate_and_save_map_summary import generate_and_save_map_summary
import pyodbc

def get_map_case_ids_needing_summary():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT top 10 id 
        FROM docketwatch.dbo.cases 
        WHERE fk_tool = 12 AND status = 'Tracked' AND summarize IS NULL
    """)
    results = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results

def main():
    for case_id in get_map_case_ids_needing_summary():
        print(f"→ Summarizing MAP case {case_id}")
        generate_and_save_map_summary(case_id)

if __name__ == "__main__":
    main()
