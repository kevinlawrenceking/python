import re

def convert_last_first_to_proper(name):
    """
    Converts a party name from "LAST, FIRST" to "First Last" and normalizes spacing/casing.
    """
    name = name.strip()
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        formatted_name = f"{first} {last}"
    else:
        formatted_name = name

    # Remove extra spaces and convert to title case
    formatted_name = re.sub(r'\s+', ' ', formatted_name).title()

    return formatted_name
