import pyodbc
import re
from datetime import datetime

# **Database Connection**
DB_CONNECTION = "DSN=Docketwatch;TrustServerCertificate=yes;"
conn = pyodbc.connect(DB_CONNECTION)
cursor = conn.cursor()

# ** Function to Convert to Proper Case **
def to_proper_case(name):
    """Converts a name to Proper Case (First Letter Capitalized)."""
    words = name.split()
    return " ".join(word.capitalize() for word in words)

# ** Function to Convert "Last, First Middle" to "First Middle Last" **
def convert_last_first_to_proper(name):
    """Converts 'Last, First Middle' format to 'First Middle Last'."""
    if "," in name:
        parts = name.split(",", 1)
        last_name = parts[0].strip()
        first_middle = parts[1].strip() if len(parts) > 1 else ""
        return to_proper_case(f"{first_middle} {last_name}")
    return name  # Return as-is if no comma found

# ** Function to Clean Case Name **
def clean_case_name(case_name, county_code):
    """Cleans and normalizes the case name based on the county's rules."""
    cleaned_name = case_name.strip()
    
    # ** Standard Cleaning for LAC Cases **
    if county_code == "LAC":
        replace_patterns = [
            "Approval Of Minor'S Contract - ", "APPROVAL OF MINOR'S CONTRACT -", "Joint Petition Of:",
            "LIVING TRUST DATED", "REVOCABLE LIVING TRUST", "SPECIAL NEEDS TRUST",
            "Revocable Living Trust", "Family Trust", "Irrevocable Trust", "Living Trust",
            "trust udt", "Dated [A-Za-z]+ [0-9]+,", "SUBTRUSTS CREATED THEREUNDER",
            "Dated June ", " inc "
        ]
        for pattern in replace_patterns:
            cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)
        
        # ** Remove Month Names & Common Phrases **
        months = ["January", "February", "March", "July", "August", "September", "October", "November", "December",
                  "TRUST UDT", "LIVING TRUST", "FAMILY TRUST", "REVOCABLE TRUST", "TRUST "]
        for month in months:
            cleaned_name = re.sub(rf"\b{month}\b", "", cleaned_name, flags=re.IGNORECASE)
        
        # ** Remove "VS" or "AND" and replace with "|" for party separation **
        cleaned_name = re.sub(r"\s(VS\.?|AND)\s", "|", cleaned_name, flags=re.IGNORECASE)

    elif county_code == "NYC":
        cleaned_name = re.sub(r"\sv\.?\s", "|", cleaned_name, flags=re.IGNORECASE)

    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()  # Remove extra spaces
    return cleaned_name

# ** Function to Check for and Insert Case Parties **
def process_case_parties(case_id, case_name, county_code):
    """Processes parties for a case, inserts into case_parties if not exist."""
    # ** Clean Case Name **
    cleaned_case_name = clean_case_name(case_name, county_code)
    
    # ** Split Case Name into Parties **
    parties = cleaned_case_name.split("|")
    unique_parties = set()

    for party in parties:
        party = party.strip()
        
        # ** Convert Name Format if LAC **
        if county_code == "LAC":
            party = convert_last_first_to_proper(party)
        
        if party and party not in unique_parties:
            unique_parties.add(party)
            
            # ** Insert Party if Not Exists **
            cursor.execute("""
                INSERT INTO docketwatch.dbo.case_parties (fk_case, party_name, party_role)
                SELECT ?, ?, 'Party'
                WHERE NOT EXISTS (
                    SELECT 1 FROM docketwatch.dbo.case_parties 
                    WHERE fk_case = ? AND party_name = ?
                )
            """, (case_id, party, case_id, party))
    
    return len(unique_parties)

# ** Function to Check for Celebrity Matches **
def check_celebrity_matches():
    """Finds and inserts new celebrity matches into case_celebrity_matches."""
    query = """
    INSERT INTO docketwatch.dbo.case_celebrity_matches (fk_case, fk_celebrity, celebrity_name, match_status)
    SELECT c.id, ce.id, ce.name, 'EXACT'
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.case_parties p ON p.fk_case = c.id
    INNER JOIN docketwatch.dbo.celebrities ce ON ce.name = p.party_name
    WHERE NOT EXISTS (
        SELECT 1 FROM docketwatch.dbo.case_celebrity_matches m
        WHERE m.fk_case = c.id AND m.fk_celebrity = ce.id
        AND m.match_status <> 'Removed'
    )
    UNION
    SELECT c.id, ce.id, ce.name, 'EXACT'
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.case_parties p ON p.fk_case = c.id
    INNER JOIN docketwatch.dbo.celebrity_names ca ON ca.name = p.party_name AND ca.ignore = 0
    INNER JOIN docketwatch.dbo.celebrities ce ON ce.id = ca.fk_celebrity
    WHERE NOT EXISTS (
        SELECT 1 FROM docketwatch.dbo.case_celebrity_matches m
        WHERE m.fk_case = c.id AND m.fk_celebrity = ce.id
        AND m.match_status <> 'Removed'
    );
    """
    cursor.execute(query)
    conn.commit()

# ** Process Unprocessed Cases (case_parties_checked = 0) **
cursor.execute("""
    SELECT c.id, c.case_number, c.case_name, t.name AS county_name, t.code
    FROM docketwatch.dbo.cases c
    INNER JOIN docketwatch.dbo.courts o ON c.fk_court = o.court_code
    INNER JOIN docketwatch.dbo.counties t ON o.fk_county = t.id 
    WHERE c.case_parties_checked = 0
    ORDER BY c.id ASC
""")

cases = cursor.fetchall()
total_cases = len(cases)
total_parties = 0

if total_cases > 0:
    print(f"🔄 Processing {total_cases} unprocessed cases...\n")
else:
    print("✅ No unprocessed cases found.")

for case in cases:
    case_id, case_number, case_name, county_name, county_code = case

    # ** Process Case Parties **
    num_parties = process_case_parties(case_id, case_name, county_code)
    total_parties += num_parties

    # ** Mark Case as Processed **
    cursor.execute("UPDATE docketwatch.dbo.cases SET case_parties_checked = 1 WHERE id = ?", (case_id,))
    print(f"✅ Processed Case: {case_number} | {num_parties} parties added")

# ** Check for Celebrity Matches After Processing Cases **
check_celebrity_matches()
print("\n🎯 Celebrity matches checked and updated.")

# ** Commit and Close Database Connection **
conn.commit()
cursor.close()
conn.close()

print(f"\n✅ Completed Processing {total_cases} Cases with {total_parties} Parties Inserted!")
