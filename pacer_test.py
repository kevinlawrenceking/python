import requests
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import os


def get_pacer_authenticated_session(username, password):
    """
    Authenticates with the PACER API and returns an authenticated requests.Session object.
    """
    auth_url = "https://pacer.login.uscourts.gov/services/cso-auth"
    session = requests.Session()
    payload = {
        "loginId": username,
        "password": password,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    print(f"Authenticating PACER user: {username}...")
    try:
        response = session.post(auth_url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        response_data = response.json()
        if response_data.get("loginResult") == "0" and "nextGenCSO" in response_data:
            session.cookies.set("nextGenCSO", response_data["nextGenCSO"], domain=".uscourts.gov")
            print("Authentication successful.")
            return session
        else:
            print(f"Authentication failed: {response_data.get('errorDescription', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None


def download_pdf_with_session(session, base_url, doc_url, save_path):
    try:
        print("Requesting CSRF warning page...")
        response = session.get(doc_url)
        with open("U:/tmztools/python/billing_page_debug.html", "w", encoding="utf-8") as f:
            f.write(response.text)

        soup = BeautifulSoup(response.text, "html.parser")
        csrf_form = soup.find("form", {"id": "referrer_form"})
        if not csrf_form:
            print("No CSRF form found. Wrote response to billing_page_debug.html")
            return False

        action_url = urljoin(base_url, csrf_form.get("action"))
        csrf_token = csrf_form.find("input", {"name": "csrf"}).get("value")

        print(f"Posting to CSRF form at {action_url} with token {csrf_token}")
        headers = {
            "Referer": "https://external"
        }
        data = {
            "csrf": csrf_token
        }
        pdf_frame_response = session.post(action_url, data=data, headers=headers)
        soup = BeautifulSoup(pdf_frame_response.text, "html.parser")
        iframe = soup.find("iframe")
        if not iframe:
            print("No iframe found with PDF URL.")
            return False

        pdf_url = iframe.get("src")
        if not pdf_url.startswith("http"):
            pdf_url = urljoin(base_url, pdf_url)

        print(f"Downloading PDF from: {pdf_url}")
        pdf_data = session.get(pdf_url)
        with open(save_path, "wb") as f:
            f.write(pdf_data.content)
        print(f"Saved PDF to {save_path}")
        return True

    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return False


# Example usage
if __name__ == '__main__':
    pacer_username = "TMZFEDPACER"
    pacer_password = "Courtpacer19D!"
    doc_url = "https://ecf.ilnd.uscourts.gov/doc1/067132647218"
    save_path = os.path.join("U:/tmztools/python", "test_download.pdf")

    session = get_pacer_authenticated_session(pacer_username, pacer_password)
    if session:
        download_pdf_with_session(session, "https://ecf.ilnd.uscourts.gov", doc_url, save_path)
