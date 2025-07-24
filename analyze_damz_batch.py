import pyodbc
import openai
import time
from openai import OpenAI

# Config
MODEL = "gpt-4o"
PRICE_PER_1K_TOKENS = 0.005  # both prompt + output
BATCH_LIMIT = 1000

# DB connection
conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
cursor = conn.cursor()

def get_chatgpt_key():
    cursor.execute("SELECT chatgpt_api FROM docketwatch.dbo.utilities WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else None

openai.api_key = get_chatgpt_key()
client = OpenAI(api_key=openai.api_key)

# Load format prompt
with open("\\\\10.146.176.84\\general\\docketwatch\\python\\prompt_rules.txt", "r") as f:
    FORMAT_RULES = f.read()

def build_prompt(headline, description):
    return f"""{FORMAT_RULES}

Headline: {headline}
Shot Description: {description}
"""

def analyze_asset(headline, description):
    prompt = build_prompt(headline, description)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.4,
            messages=[
                {"role": "system", "content": "You are a metadata formatting expert."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content
        usage = response.usage

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        type_line = next((l for l in lines if l.lower().startswith("type:")), None)
        headline_line = next((l for l in lines if l.lower().startswith("optimized headline:")), None)

        return (
            type_line.split(":", 1)[1].strip() if type_line else None,
            headline_line.split(":", 1)[1].strip() if headline_line else None,
            usage.prompt_tokens,
            usage.completion_tokens
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return None, None, 0, 0

# Run batch
cursor.execute(f"""
    SELECT TOP {BATCH_LIMIT} fk_asset, headline, shot_description
    FROM docketwatch.dbo.damz_test
    WHERE headline_optimized IS NULL
""")
rows = cursor.fetchall()

total_prompt_tokens = 0
total_completion_tokens = 0
processed = 0
skipped = 0

for row in rows:
    fk_asset, headline, desc = row
    print(f"Processing: {fk_asset}")
    type_final, headline_final, p_tokens, c_tokens = analyze_asset(headline, desc)

    if type_final and headline_final:
        cursor.execute("""
            UPDATE docketwatch.dbo.damz_test
            SET 
                headline_type = ?, 
                headline_type_final = ?, 
                headline_optimized = ?, 
                headline_final = ?
            WHERE fk_asset = ?
        """, (type_final, type_final, headline_final, headline_final, fk_asset))
        conn.commit()
        processed += 1
        total_prompt_tokens += p_tokens
        total_completion_tokens += c_tokens
        print(f"✓ Updated {fk_asset} | Prompt: {p_tokens}, Output: {c_tokens}")
    else:
        skipped += 1
        print(f"⚠ Skipped: {fk_asset}")

    time.sleep(1.5)

# Final cost breakdown
total_tokens = total_prompt_tokens + total_completion_tokens
total_cost = (total_tokens / 1000) * PRICE_PER_1K_TOKENS

print("\n=== BATCH SUMMARY ===")
print(f"Processed: {processed}")
print(f"Skipped: {skipped}")
print(f"Total tokens: {total_tokens} (Prompt: {total_prompt_tokens}, Output: {total_completion_tokens})")
print(f"Estimated Cost: ${total_cost:,.2f}")

cursor.close()
conn.close()
