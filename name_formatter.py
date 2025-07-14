import re

def convert_last_first_to_proper(name: str) -> str:
    """
    Converts 'Last, First Middle' to 'First Middle Last' if the name contains a comma.
    Assumes the caller only uses this function for LAC cases.
    """
    if "," in name:
        parts = name.split(",", 1)
        last_name = parts[0].strip()
        first_middle = parts[1].strip() if len(parts) > 1 else ""
        formatted_name = f"{first_middle} {last_name}".strip()
        return formatted_name.title()  # Convert to Proper Case
    return name.title()  # Otherwise, just title-case the name