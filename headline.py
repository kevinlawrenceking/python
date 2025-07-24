import pyodbc
import openai
import time
from openai import OpenAI
# Connect to Docketwatch DB
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

# Grab OpenAI key from database
def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else None

openai.api_key = get_chatgpt_key()

FORMAT_RULES = """
You are a metadata formatting assistant for a celebrity photo asset system called DAMZ.

Your job is to:
1. Identify the correct headline type from the list below.
2. Reformat the raw headline into the proper format for that type.

You must follow these exact formatting rules:

Headline - General  
Format: [Main Subject(s)], [Key Topics]  
Example: Charlie Wilson, Killer Mike, New Song Called Superman  
Refinements:
- Use only keywords (not full sentences or quotes).
- List people first, then topic.
- Remove phrases like "says", "talks about", "discusses".

Headline - Commercial  
Format: [Company or Brand Name], [Celebrity Last Name(s)], [Campaign Name OR General Topic], COMM  
Example: Dunkin, Affleck, Dunkings, COMM  
Refinements:
- Use last names only.
- Always end with COMM.
- Include campaign nickname or main topic if known.

Headline - Court  
Format: [Case Name], [Court Type], [Key Event]  
Example: CA v Rakim Mayers, Criminal, Verdict Reached  
Refinements:
- Use "CA v [Last Name]" format.
- Include court type (Criminal, Civil, etc.).
- Use event phrases like "Verdict Reached" or "Sentencing".

Headline - Government  
Format: [Government Agency OR Event], [Key Figures], [Topic]  
Example: White House, Trump, Musk, Signing Executive Orders In Oval Office  
Refinements:
- Start with entity (e.g., White House).
- Follow with people (last names only).
- Use clean, action-based summary.

Headline - Movie Clip  
Format: [Movie Title], [Actor Last Names], [Scene or Event]  
Example: Beetlejuice, Lutz, Shadix, O'Hara, Cavett, Kellerman, Dinner Scene  
Refinements:
- Use actor last names only.
- Use concise description of scene.
- No "publicity still" language.

Headline - Music Video  
Format: [Artist Last Name(s) OR Band Name], [Song Title]  
Example: Carpenter, Please Please Please  
Refinements:
- Do not include the phrase "music video".
- List artist or band name followed by song title.

Headline - Police Images  
Format: [Police Department OR Main Subject], [Action]  
Example: NYPD, Arrest of Pro-Palestinian Protesters  
Refinements:
- Use department abbreviation (e.g., NYPD).
- Focus on what occurred, not where or when.

Headline - Presser  
Format: [Organizing Agency], [Key Figures], [Main Topic]  
Example: White House, Trump, Starmer, Peace Deal for Ukraine  
Refinements:
- No intro phrases (e.g., "during", "at").
- List key names (last name only).
- End with short topic.

Headline - Social Media  
Format: [Key Person(s)], [Event or Topic]  
Example: Trachtenberg, Hannigan, Tributes to Trachtenberg, Passing  
Refinements:
- Always lead with main celebrity.
- If applicable, include secondary name or source.
- Keep topic tight and event-specific.

Headline - Trailer  
Format: [Movie OR TV Show Title], [Release Year], TRAILER  
Example: Superman 2025, TRAILER  
Refinements:
- Do not include actor or director.
- Always end with TRAILER.

Headline - TV Show  
Format: [Show Title], S[Season #], E[Episode #], [Key People], [General Topic]  
Example: Hell's Kitchen, S10, E203, Ramsey, Chefs Compete  
Refinements:
- Use "S#" and "E#" format.
- Include celebrity or host last name.
- Concise episode summary.

Headline - Live Event  
Format: [Event Name], [Teams OR Key Figures], [Action or Segment]  
Examples:
- Lakers vs Knicks, Celebrity Cameo
- 97th Annual Academy Awards, Red Carpet  
Refinements:
- Start with event name.
- For sports, include teams.
- For award shows, include segment (e.g., Red Carpet).

Formatting Rules Summary:
- Use only last names for celebrities.
- No quotes, no filler, no location details unless required.
- Headline must be concise and match the structural format for its type.
- Use tags like COMM, TRAILER, PRESSER only when defined by format.

You must return exactly two lines:
Type: [exact type name]  
Optimized Headline: [final cleaned and formatted headline]
"""


def build_prompt(headline, description):
    return f"""{FORMAT_RULES}

Headline: {headline}
Shot Description: {description}
"""

def analyze_asset(headline, description):
    prompt = build_prompt(headline, description)
    try:
        client = openai.OpenAI(api_key=get_chatgpt_key())

        response = client.chat.completions.create(
            model="gpt-4",
            temperature=0.4,
            messages=[
                {"role": "system", "content": "You are a metadata formatting expert."},
                {"role": "user", "content": prompt}
            ]
        )
        text = response.choices[0].message.content

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        type_line = next((l for l in lines if l.lower().startswith("type:")), None)
        headline_line = next((l for l in lines if l.lower().startswith("optimized headline:")), None)
        return (
            type_line.split(":", 1)[1].strip() if type_line else None,
            headline_line.split(":", 1)[1].strip() if headline_line else None
        )
    except Exception as e:
        print(f"Error during AI call: {e}")
        return None, None

# Fetch unprocessed rows from damz_test
cursor.execute("""
    SELECT TOP 1000 fk_asset, headline, shot_description
    FROM docketwatch.dbo.damz_test
    WHERE headline_optimized IS NULL
""")
rows = cursor.fetchall()

for row in rows:
    fk_asset, raw_headline, shot_description = row
    print(f"\nAnalyzing asset: {fk_asset}")

    headline_type, headline_optimized = analyze_asset(raw_headline, shot_description)

    if headline_type and headline_optimized:
        cursor.execute("""
            UPDATE docketwatch.dbo.damz_test
            SET headline_type = ?, headline_type_final = ?,headline_optimized = ?, headline = ?
            WHERE fk_asset = ?
        """, (headline_type, headline_type, headline_optimized, headline_optimized, fk_asset))
        conn.commit()
        print(f"Updated: {fk_asset}")
    else:
        print(f"Skipped: {fk_asset} — AI result incomplete or invalid")

    time.sleep(1.5)

cursor.close()
conn.close()
print("DONE.")
