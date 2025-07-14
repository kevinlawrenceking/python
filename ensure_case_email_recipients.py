import json

def ensure_case_email_recipients(cursor, case_id):
    """
    For a given case_id, check the tool's owners and insert missing recipients into case_email_recipients.
    Should be called before sending email alerts.
    """
    # Get the owners JSON array for the tool linked to this case
    cursor.execute("""
        SELECT t.owners
        FROM docketwatch.dbo.cases c
        INNER JOIN docketwatch.dbo.tools t ON c.fk_tool = t.id
        WHERE c.id = ?
    """, (case_id,))
    row = cursor.fetchone()

    if not row or not row.owners:
        return  # No tool or no owners assigned

    try:
        owners = json.loads(row.owners)
    except Exception as e:
        logging.warning(f"Invalid JSON in owners field for case {case_id}: {e}")
        return

    for username in owners:
        username = username.strip()

        # Confirm the user exists
        cursor.execute("""
            SELECT username FROM docketwatch.dbo.users WHERE username = ?
        """, (username,))
        if cursor.fetchone():
            # Check if this case-user combo already exists
            cursor.execute("""
                SELECT 1 FROM docketwatch.dbo.case_email_recipients
                WHERE fk_case = ? AND fk_username = ?
            """, (case_id, username))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO docketwatch.dbo.case_email_recipients (fk_case, fk_username)
                    VALUES (?, ?)
                """, (case_id, username))
                logging.info(f"Added {username} to case_email_recipients for case {case_id}")
