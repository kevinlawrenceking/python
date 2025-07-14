from scraper_base import get_db_cursor, send_case_update_alert

def main():
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("""
            SELECT id
            FROM docketwatch.dbo.case_updates
            WHERE emailed = 0 AND is_storyworthy = 1
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        for row in rows:
            send_case_update_alert(cursor, row.id)
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
