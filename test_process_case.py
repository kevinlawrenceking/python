
from case_processing import process_case

# Dummy test values
case_id = 105949
case_number = "000331-2025"
case_name = "CAPITAL ONE, N.A. v. AMANDA M HANLEY"
court_code = "LIVI"
county_code = "NYC"

print("Calling process_case()...")
process_case(case_id, case_number, case_name, court_code, county_code)
print("Finished calling process_case().")
