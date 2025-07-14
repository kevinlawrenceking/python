import requests

PACER_USERNAME = "TMZFEDPACER"
PACER_PASSWORD = "Courtpacer19D!"
PACER_CLIENT_CODE = "tmztest"
PACER_OTP = None

LOGIN_URL = "https://pacer.login.uscourts.gov/services/cso-auth"
TARGET_COURT_URL = "https://ecf.nvd.uscourts.gov/cgi-bin/login.pl"

session = requests.Session()

def authenticate():
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "loginId": PACER_USERNAME,
        "password": PACER_PASSWORD,
        "redactFlag": "1",
        "clientCode": PACER_CLIENT_CODE
    }
    if PACER_OTP:
        payload["otpCode"] = PACER_OTP

    response = session.post(LOGIN_URL, headers=headers, json=payload)
    data = response.json()

    if data.get("loginResult") == "0":
        session.cookies.set("nextGenCSO", data["nextGenCSO"], domain=".uscourts.gov")
        print("Token stored in session.")
    else:
        raise Exception("PACER login failed: " + data.get("errorDescription", "Unknown error"))

def access_case_portal():
    response = session.get(TARGET_COURT_URL, allow_redirects=True)
    print("Final URL:", response.url)
    print("Status code:", response.status_code)
    print("Response preview:", response.text[:500])

if __name__ == "__main__":
    authenticate()
    access_case_portal()
