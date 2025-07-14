"""
Generate HTML Summaries from existing Gemini text summaries.
Only processes records where `summarize` is set but `summarize_html` is NULL.
"""

import pyodbc
import markdown2
from bs4 import BeautifulSoup

# --- DB Connection ---
def get_db_cursor():
    conn = pyodbc.connect("DSN=docketwatch;Trusted_Connection=yes;")
    return conn, conn.cursor()

# --- HTML Cleanup ---
def clean_case_summary_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # 1. Remove redundant summary header
    for p in soup.find_all("p"):
        if p.text.strip().startswith("Case Summary:"):
            p.decompose()
            break

    # 2. Inject <br/>s between key metadata items
    for p in soup.find_all("p"):
        if "Case Name:" in p.decode_contents() and "Case Number:" in p.decode_contents():
            new_html = p.decode_contents()
            new_html = new_html.replace("<strong>Case Number:", "<br/><strong>Case Number:")
            new_html = new_html.replace("<strong>Jurisdiction:", "<br/><strong>Jurisdiction:")
            new_html = new_html.replace("<strong>Presiding Judge:", "<br/><strong>Presiding Judge:")
            p.clear()
            p.append(BeautifulSoup(new_html, "html.parser"))
            break

    # 3. Replace <p><strong>XYZ:</strong></p> with <h3>XYZ</h3>
    for p in soup.find_all("p"):
        if len(p.contents) == 1 and p.contents[0].name == "strong":
            content = p.contents[0].text.strip()
            if content.endswith(":"):
                content = content[:-1]
            h3 = soup.new_tag("h3")
            h3.string = content
            p.replace_with(h3)

    return str(soup)

# --- Convert summaries ---
def convert_summaries():
    conn, cursor = get_db_cursor()
    cursor.execute("""
        SELECT id, summarize 
        FROM docketwatch.dbo.cases 
        WHERE summarize IS NOT NULL AND summarize_html IS NULL
    """)
    rows = cursor.fetchall()

    print(f"Found {len(rows)} summaries to convert.")
    for case_id, summary in rows:
        try:
            html = markdown2.markdown(summary)
            html_clean = clean_case_summary_html(html)
            cursor.execute(
                "UPDATE docketwatch.dbo.cases SET summarize_html = ? WHERE id = ?",
                (html_clean, case_id)
            )
            print(f"Updated case ID {case_id} with HTML summary.")
        except Exception as e:
            print(f"Error processing case {case_id}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    convert_summaries()
