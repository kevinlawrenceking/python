import pyodbc
import subprocess

def get_tracked_cases():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT top 30 id 
        FROM docketwatch.dbo.cases 
        WHERE fk_tool = 2 AND status = 'Tracked' AND summarize IS NULL
        order by fk_priority desc
    """)
    ids = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return ids

def run_summarizer(case_id):
    print(f"Summarizing case {case_id}...")

    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET summarize = 'Attempting summary'
            WHERE id = ?
        """, (case_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[!] Failed to mark case {case_id} as 'Attempting summary': {e}")

    subprocess.run([
        "python",
        r"\\10.146.176.84\general\docketwatch\python\pacer_case_summarizer.py",
        "--case-id",
        str(case_id)
    ])


def main():
    case_ids = get_tracked_cases()
    print(f"Found {len(case_ids)} unsummarized cases.")
    for cid in case_ids:
        run_summarizer(cid)

if __name__ == "__main__":
    main()
