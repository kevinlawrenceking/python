import requests
import json

def call_gemini_generate_content(api_key, model_name, prompt):
    """
    Calls the Gemini API's generateContent method with the specified model.

    Args:
        api_key (str): Your Google Gemini API key.
        model_name (str): The name of the Gemini model to use (e.g., "gemini-2.0-flash").
        prompt (str): The text prompt to send to the model.
    """
    # The full model path needs to be prefixed with "models/"
    full_model_path = f"models/{model_name}"
    
    # API endpoint for generateContent
    url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_path}:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    print(f"Calling model: {full_model_path}")
    print(f"Prompt: '{prompt}'")

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        response_data = response.json()

        if response_data and "candidates" in response_data and response_data["candidates"]:
            # Extract the text from the first candidate's first part
            generated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            print("\nGenerated Content:")
            print(generated_text)
        else:
            print("No content generated or unexpected response structure.")
            print(json.dumps(response_data, indent=2))

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
    except KeyError as key_err:
        print(f"Key error occurred while parsing response: {key_err} - Response: {json.dumps(response_data, indent=2)}")


# Your API key
gemini_api_key = "AIzaSyDYoUOVLnzw8JHIpVwcEknMRccLSlFuxBc"

# Try using a known good model for content generation
# You can also try "gemini-1.5-pro" or "gemini-1.5-flash"
model_to_use = "gemini-2.0-flash" 
user_prompt = "Tell me a short, inspiring quote about perseverance."

if __name__ == "__main__":
    call_gemini_generate_content(gemini_api_key, model_to_use, user_prompt)
