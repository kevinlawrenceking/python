# main.py - Celebrity synchronization script
import pyodbc
import logging

# Setup Logging
LOG_FILE = "celebrity_update.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Database Connection
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
try:
    conn = pyodbc.connect(DB_CONNECTION)
    cursor = conn.cursor()
    logging.info("Connected to DocketWatch database successfully.")
except Exception as e:
    logging.error(f"Error connecting to database: {e}")
    exit(1)

def find_new_celebrities():
    """Finds celebrities in DAMZ not already in DocketWatch."""
    query = """
    SELECT  
        p.id, 
        COUNT(*) AS appearances,
        REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '') AS celebrity_name,
        DATEDIFF(DAY, MAX(a.created_at), GETDATE()) AS days_since_last_asset
    FROM [damz].[dbo].[asset_metadata] m
    INNER JOIN [damz].[dbo].[asset] a ON a.id = m.fk_asset
    INNER JOIN [damz].[dbo].[picklist_celebrity] p 
        ON p.name = REPLACE(REPLACE(REPLACE(m.celebrity_in_photo, '[', ''), ']', ''), '"', '')
    WHERE a.created_at >= DATEADD(YEAR, -5, GETDATE())  
      AND m.celebrity_in_photo IS NOT NULL 
      AND m.celebrity_in_photo <> '[]' 
      AND m.celebrity_in_photo <> '["Not Applicable"]'
    GROUP BY p.id, m.celebrity_in_photo
    HAVING COUNT(*) > 1 
      AND p.id NOT IN (SELECT id FROM [docketwatch].[dbo].[celebrities])
    """
    cursor.execute(query)
    return cursor.fetchall()

def insert_celebrity(celeb):
    """Inserts a new celebrity into DocketWatch."""
    celeb_id, appearances, celeb_name, days_since_last_asset = celeb

    query = """
    INSERT INTO docketwatch.dbo.celebrities (
        id, name, appearances, days_since_last_asset, 
        probability_score, relevancy_index, docketwatch_index, critical_celeb
    )
    SELECT ?, ?, ?, ?, ?, ?, ?, ?
    WHERE NOT EXISTS (
        SELECT 1 FROM docketwatch.dbo.celebrities WHERE id = ?
    )
    """
    
    # Default values for new celebrities
    probability_score = 0.0
    relevancy_index = 0.0
    docketwatch_index = 0.0
    critical_celeb = 0  # New celebrities are not manually flagged unless assigned later
    
    cursor.execute(query, (
        celeb_id, celeb_name, appearances, days_since_last_asset,
        probability_score, relevancy_index, docketwatch_index, critical_celeb,
        celeb_id
    ))
    conn.commit()


def main():
    logging.info("Starting celebrity synchronization process.")
    new_celebrities = find_new_celebrities()
    inserted_count = 0
    
    for celeb in new_celebrities:
        insert_celebrity(celeb)
        inserted_count += 1
    
    logging.info(f"Inserted {inserted_count} new celebrities into DocketWatch.")
    print(f"Inserted {inserted_count} new celebrities into DocketWatch.")
    
    conn.close()
    logging.info("Celebrity synchronization process completed.")

if __name__ == "__main__":
    main()
