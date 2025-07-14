import pyodbc
import unicodedata

def sanitize_unicode(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    replacements = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\xa0": " ",
        "â€“": "-", "â€”": "-", "â€™": "'", "â€œ": '"', "â€": '"',
        "â€˜": "'", "â€": '"'
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text

def clean_existing_summaries():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, summarize, summarize_html
        FROM docketwatch.dbo.cases
        WHERE summarize IS NOT NULL OR summarize_html IS NOT NULL
    """)
    rows = cursor.fetchall()
    print(f"Found {len(rows)} rows to sanitize.")

    for row in rows:
        case_id, summary, html = row
        summary_cleaned = sanitize_unicode(summary or "")
        html_cleaned = sanitize_unicode(html or "")

        cursor.execute("""
            UPDATE docketwatch.dbo.cases
            SET summarize = ?, summarize_html = ?
            WHERE id = ?
        """, (summary_cleaned[:4000], html_cleaned[:8000], case_id))

    conn.commit()
    print("Sanitization complete.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    clean_existing_summaries()
