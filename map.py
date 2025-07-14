import requests

# Initialize session
session = requests.Session()

# Step 1: GET the OAuth2 authorize page to initialize cookies and CSRF token
auth_url = (
    "https://calcourts02b2c.b2clogin.com/"
    "calcourts02b2c.onmicrosoft.com/b2c_1_media-lasc-susi/"
    "oauth2/v2.0/authorize"
    "?client_id=64f6a02f-a3d7-4871-a7b0-0883a24bdbda"
    "&redirect_uri=https%3A%2F%2Fmedia.lacourt.org%2Fsignin-oidc"
    "&response_type=code%20id_token"
    "&scope=openid%20profile%20offline_access%20https%3A%2F%2Fcalcourts02b2c.onmicrosoft.com%2Fapi%2Fread"
    "&response_mode=form_post"
    "&nonce=random"
    "&state=random"
)

print("[*] Loading auth page...")
session.get(auth_url)

# Step 2: Extract CSRF token from cookies
csrf_token = session.cookies.get("x-ms-cpim-csrf")
if not csrf_token:
    print("❌ Failed to get CSRF token.")
    print(session.cookies.get_dict())
    exit()

print(f"[+] CSRF token captured: {csrf_token[:10]}...")

# Step 3: Submit login
login_url = (
    "https://calcourts02b2c.b2clogin.com/"
    "calcourts02b2c.onmicrosoft.com/B2C_1_Media-LASC-SUSI/SelfAsserted"
    "?tx=StateProperties=eyJUSUQiOiI3YzNjMWE5NS0zOTM3LTQ4ZWQtODcxNS0zYTVkOTBmM2NjY2YifQ"
    "&p=B2C_1_Media-LASC-SUSI"
)

payload = {
    "request_type": "RESPONSE",
    'logonIdentifier': 'priscilla.hwang@tmz.com',
    'password': 'P12isci11@'
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-CSRF-TOKEN": csrf_token,
    "X-Requested-With": "XMLHttpRequest",
    "Referer": auth_url,
    "Origin": "https://calcourts02b2c.b2clogin.com",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

print("[*] Submitting login...")
response = session.post(login_url, data=payload, headers=headers)

# Step 4: Verify login success via cookies
auth_cookies = session.cookies.get_dict()
if ".AspNetCore.Cookies" in auth_cookies or any("cpim" in k for k in auth_cookies):
    print(" Login successful!")
else:
    print(" Login failed.")
    print(response.text)
    exit()

# Step 5: Lookup a case by case number
case_number = '25SMCV01570'  #  Change to test others
case_lookup_url = f'https://media.lacourt.org/api/AzureApi/GetCaseList/{case_number}'

print(f"[*] Looking up case {case_number}...")
case_response = session.get(case_lookup_url)

# Step 6: Print raw result and debug response content
print(f"[DEBUG] Status: {case_response.status_code}")
print(f"[DEBUG] Headers: {case_response.headers}")
print(f"[DEBUG] Content:\n{case_response.text[:1000]}")  # Show first 1000 characters of response

# Try parsing as JSON only if response looks valid
try:
    data = case_response.json()
except Exception as e:
    print(" Failed to parse JSON:", e)
    exit()

# Step 7: Process JSON if valid
if data.get("IsSuccess") and data["ResultList"]:
    non_criminal = data["ResultList"][0].get("NonCriminalCases", [])
    if non_criminal:
        case = non_criminal[0]
        print(f" Case found: {case['CaseTitle']} (Judge: {case['JudicialOfficer']})")
    else:
        print(" Case exists but no non-criminal case data found.")
else:
    print(f"API error: {data.get('ErrorMessage')}")

