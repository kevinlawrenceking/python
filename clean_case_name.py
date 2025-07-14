import re

def clean_case_name(case_name: str, county_code: str) -> str:
    """Cleans a case name based on the county_code (LAC or NYC)."""
    
    # Standard Trim
    cleaned_name = case_name.strip()

    if county_code == "LAC":
        # Find & Replace Common Phrases for LAC
        patterns = [
            r"Approval Of Minor'S Contract - ", r"APPROVAL OF MINOR'S CONTRACT -",
            r"Joint Petition Of:", r"LIVING TRUST DATED", r"REVOCABLE LIVING TRUST",
            r"SPECIAL NEEDS TRUST", r"Revocable Living Trust|Family Trust|Irrevocable Trust|Living Trust",
            r"Family Trust", r"Living Trust", r"trust udt",
            r"Dated [A-Za-z]+ [0-9]+,", r" ?- ?(CONSERVATORSHIP|DECEDENT|GUARDIANSHIP|IN THE MATTER OF|MINOR'S COMPROMISE)",
            r" APPROVAL OF MINOR'S CONTRACT -", r"SUBTRUSTS CREATED THEREUNDER",
            r"Dated June ", r" inc ", r"Trust April", r"TRUST JUNE"
        ]

        for pattern in patterns:
            cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)

        # Remove Full Month Names
        months = [
            "inter vivos", "a minor marriage of", "special needs", "revocable",
            "January", "February", "March", "July", "August", "September", "October", "November", "December",
            "TRUST UDT", "LIVING TRUST", "FAMILY TRUST", "REVOCABLE TRUST", "TRUST"
        ]

        for month in months:
            cleaned_name = re.sub(rf"\b{month}\b", "", cleaned_name, flags=re.IGNORECASE)

        # Final Cleanup for LAC
        cleaned_name = re.sub(r"\s*Trust, Dated.*", "", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"\s*(Revocable Living Trust|Family Trust|Irrevocable Trust)", "", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"^The\s+", "", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"\s*Trust$", "", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"[0-9/]", "", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"\s+,", ",", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"\s+", " ", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"Dated", "", cleaned_name, flags=re.IGNORECASE)

    elif county_code == "NYC":
        # NYC: Remove Jurisdictional Phrases
        patterns = [
            r"\b(et al\.?)\b", r"\b(the people of the state of new york)\b",
            r"\b(state of new york)\b", r"\b(the city of new york)\b",
            r"\b(city of new york)\b", r"\b(county of [A-Z ]+)\b",
            r"\b(in re|ex parte)\b",
            r"an infant under the age of [0-9]+ years by his father and natural guardian,",
            r"d/b/a\s+[A-Z0-9 ]+"
        ]

        for pattern in patterns:
            cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)

        # Replace " v. " with " | "
        cleaned_name = re.sub(r"\sv\.?\s", " | ", cleaned_name, flags=re.IGNORECASE)

        # Final Cleanup for NYC
        cleaned_name = re.sub(r"\s+", " ", cleaned_name, flags=re.IGNORECASE)
        cleaned_name = cleaned_name.strip()

    return cleaned_name.strip()
