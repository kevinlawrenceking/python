def check_celebrity_matches():
    """
    Checks for new celebrity matches in case_parties and inserts matches into case_celebrity_matches.
    """
    import pyodbc

    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    query = """
    INSERT INTO docketwatch.dbo.case_celebrity_matches (fk_case, fk_celebrity, celebrity_name, match_status)

SELECT c.id, ce.id, ce.name, 'Review'
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.case_parties p 
        ON p.fk_case = c.id
    INNER JOIN docketwatch.dbo.celebrity_names ca 
        ON ca.name = p.party_name 
           AND ca.ignore <> 1
    INNER JOIN docketwatch.dbo.celebrities ce 
        ON ce.id = ca.fk_celebrity
		and ce.ignore <> 1
    WHERE ca.type <> 'Alias' and NOT EXISTS (
        SELECT 1 
        FROM docketwatch.dbo.case_celebrity_matches m
        WHERE m.fk_case = c.id 
          AND m.fk_celebrity = ce.id
          AND m.match_status <> 'Removed'
    ) 
    """

    cursor.execute(query)
    conn.commit()
    cursor.close()
    conn.close()