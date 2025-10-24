import requests
import json

# --- CONFIG ---
AUTH_URL = "https://tmzs.auth0.com/oauth/token"
CMS_URL = "https://cms.tmz.com/pbjx/tmz.news.request/search-articles-request"

CLIENT_ID = "Tf7q5fODBbPuW7H7eKRqjnvw29NzhyZs"
USERNAME = "kevin.king@tmz.com"
PASSWORD = "Rimshot7135!"
REALM = "Username-Password-Authentication"

# --- STEP 1: Authenticate to Auth0 ---
auth_payload = {
    "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
    "client_id": CLIENT_ID,
    "username": USERNAME,
    "password": PASSWORD,
    "realm": REALM,
    "audience": "https://api.tmz.com/",
    "scope": "openid profile email"
}

auth_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

auth_resp = requests.post(AUTH_URL, headers=auth_headers, json=auth_payload)
auth_resp.raise_for_status()
access_token = auth_resp.json()["access_token"]

print("Authenticated. Token acquired.")

# --- STEP 2: Perform article search ---
search_payload = {
    "_schema": "pbj:tmz:news:request:search-articles-request:1-0-0",
    "request_id": "demo-query-court",
    "occurred_at": "1760979814901000",
    "ctx_retries": 0,
    "ctx_app": {
        "_schema": "pbj:gdbots:contexts::app:1-0-0",
        "vendor": "tmz",
        "name": "cms",
        "version": "0.29.0",
        "build": "2005aa0"
    },
    "q": "court",
    "count": 10,
    "page": 1,
    "autocomplete": False,
    "parsed_query_json": None,
    "is_unlisted": 0,
    "is_locked": 2,
    "sort": "order-date-desc"
}

search_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}"
}

search_resp = requests.post(CMS_URL, headers=search_headers, json=search_payload)
search_resp.raise_for_status()
data = search_resp.json()

print("\n--- Search Results ---")
for node in data.get("nodes", []):
    title = node.get("headline") or node.get("title") or "No Title"
    print(f"- {title}")

print("\nRaw response saved to 'cms_search_output.json'")
with open("cms_search_output.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
