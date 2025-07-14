from clean_case_name import clean_case_name  # Import the function
from convertLastFirstToProper import convert_last_first_to_proper # Import functions
def process_case(case_id, case_number, case_name, court_code, county_code):
    """
    Processes a case by cleaning the case name, extracting parties,
    and inserting them into case_parties.
    """
    import pyodbc
    import re
    convert_last_first_to_proper

    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()

    # Clean Case Name using the external function
    cleaned_name = clean_case_name(case_name, county_code)
    print(f"Processing case {case_number}: Cleaned name is: '{cleaned_name}'")
    
    # Normalize delimiters based on county_code
    if county_code == "LAC":
        normalized_name = re.sub(r"\s(VS\.?|AND)\s", "|", cleaned_name, flags=re.IGNORECASE)
        print("Using LAC normalization on case name.")
    else:
        normalized_name = cleaned_name.replace(" v. ", "|")
        print("Using NYC normalization on case name.")

    print(f"Normalized case name: '{normalized_name}'")
    parties = normalized_name.split("|")
    print(f"Found parties: {parties}")

    for party in parties:
        party = party.strip()

        if county_code == "LAC":
            party = convert_last_first_to_proper(party)
        else:
            party = party.title()

        print(f"Inserting party: '{party}' for case_id: {case_id}")
        query = """
            INSERT INTO docketwatch.dbo.case_parties (fk_case, party_name, party_role)
            SELECT ?, ?, 'Party'
            WHERE NOT EXISTS (
                SELECT 1 FROM docketwatch.dbo.case_parties 
                WHERE fk_case = ? AND party_name = ?
            )
        """
        params = (case_id, party, case_id, party)
        print("Executing query:")
        print(query)
        print("With parameters:", params)
        try:
            cursor.execute(query, params)
            conn.commit()
            print(f"Inserted party: '{party}' for case_id: {case_id}")
        except Exception as e:
            print(f"Error inserting party '{party}' for case_id {case_id}: {e}")
