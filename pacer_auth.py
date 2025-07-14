import requests
import json

def get_pacer_authenticated_session(username, password):
    """
    Authenticates with the PACER API and returns an authenticated requests.Session object.

    This function takes a PACER username and password, calls the official
    PACER Authentication API, and sets up a session with the necessary
    authentication cookie (nextGenCSO) for subsequent web scraping.

    Args:
        username (str): The user's PACER login username.
        password (str): The user's PACER login password.

    Returns:
        requests.Session: An authenticated session object if login is successful.
                          The session will contain the necessary cookies to access
                          PACER court websites.
        None: Returns None if authentication fails for any reason (e.g., bad
              credentials, network error, API change).
    """
    # The official URL for the PACER Authentication API
    auth_url = "https://pacer.login.uscourts.gov/services/cso-auth"

    # We use a requests.Session object to persist cookies across requests.
    # This is crucial for maintaining the login session.
    session = requests.Session()

    # The payload (data) sent to the API, as specified by PACER's documentation.
    # It must be a JSON object containing the login credentials.
    payload = {
        "loginId": username,
        "password": password,
    }

    # The headers tell the API that we are sending JSON data.
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print(f"Attempting to authenticate PACER user: {username}...")

    try:
        # Make the POST request to the authentication endpoint
        response = session.post(auth_url, headers=headers, data=json.dumps(payload), timeout=30)

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Parse the JSON response from the API
        response_data = response.json()

        # Check if the login was successful. According to docs, 'loginResult' is '0' for success.
        if response_data.get("loginResult") == "0" and "nextGenCSO" in response_data:
            cso_token = response_data["nextGenCSO"]
            print("Authentication successful.")

            # Manually set the cookie in the session. The `requests` Session object
            # will now automatically include this cookie in all subsequent requests
            # made with this session object.
            session.cookies.set("nextGenCSO", cso_token, domain=".uscourts.gov")
            
            print("Session cookie (nextGenCSO) has been set.")
            return session
        else:
            # Handle failed login attempts (e.g., wrong password)
            error_desc = response_data.get("errorDescription", "No error description provided.")
            print(f"Authentication failed: {error_desc}")
            return None

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response Body: {response.text}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"A network or request error occurred: {req_err}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse JSON response from the server.")
        return None

# --- HOW TO USE THIS FUNCTION IN YOUR SCRIPT ---

# 1. Your existing code to get credentials from the database
#    (This is just an example, replace with your actual code)
def get_credentials_from_db():
    # Replace this with your database logic
    pacer_username = "TMZFEDPACER"
    pacer_password = "Courtpacer19D!"
    return pacer_username, pacer_password

if __name__ == '__main__':
    # Retrieve credentials as you normally would
    my_username, my_password = get_credentials_from_db()

    # Call the function to get an authenticated session
    pacer_session = get_pacer_authenticated_session(my_username, my_password)

    # If the session is created successfully, you can now use it to scrape
    if pacer_session:
        print("\nAuthenticated session created successfully. You can now use this session for scraping.")
        
        # EXAMPLE: Use the authenticated session to access a specific case URL
        # Replace this with one of the case URLs you are tracking
        case_url_to_scrape = "https://ecf.flsd.uscourts.gov/cgi-bin/iqquerymenu.pl?677846" # Example URL

        print(f"Attempting to access case URL: {case_url_to_scrape}")
        try:
            case_page_response = pacer_session.get(case_url_to_scrape)
            case_page_response.raise_for_status()
            
            # Now you can use BeautifulSoup or other tools to parse case_page_response.text
            # For example: from bs4 import BeautifulSoup
            # soup = BeautifulSoup(case_page_response.text, 'html.parser')
            print("Successfully accessed the case page.")
            print(f"Status Code: {case_page_response.status_code}")
            # print("First 500 characters of page:")
            # print(case_page_response.text[:500])

        except requests.exceptions.RequestException as e:
            print(f"Failed to access the case page: {e}")

    else:
        print("\nCould not create an authenticated session. Please check credentials and network.")

