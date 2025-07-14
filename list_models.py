import requests
import json

def list_gemini_models(api_key):
    """
    Fetches and prints a list of available Gemini API models and their supported actions.

    Args:
        api_key (str): Your Google Gemini API key.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

    print(f"Fetching models from: {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        models_data = response.json()

        if "models" in models_data:
            print("\nAvailable Gemini Models:")
            for model in models_data["models"]:
                model_name = model.get("name", "N/A")
                supported_actions = model.get("supported_actions", [])
                print(f"- Model: {model_name}")
                if supported_actions:
                    print(f"  Supported Actions: {', '.join(supported_actions)}")
                else:
                    print("  No supported actions listed.")
        else:
            print("No 'models' key found in the response. Full response:")
            print(json.dumps(models_data, indent=2))

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An unexpected request error occurred: {req_err}")
    except json.JSONDecodeError as json_err:
        print(f"Failed to decode JSON response: {json_err} - Response text: {response.text}")


# Replace "YOUR_API_KEY" with the API key you provided
gemini_api_key = "AIzaSyDYoUOVLnzw8JHIpVwcEknMRccLSlFuxBc"

if __name__ == "__main__":
    list_gemini_models(gemini_api_key)
