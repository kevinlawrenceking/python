import vertexai
from google.oauth2 import service_account
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold
)

# --- CONFIGURATION ---
# The path to your service account key file
CREDENTIALS_PATH = "U:/docketwatch/vertex/tmz-docketwatch-prod-3c1d09714a96.json"

# Your project information
PROJECT_ID = "tmz-docketwatch-prod"
LOCATION = "us-central1"  # Start with the primary location

# The stable model ID we found in your console screenshot
MODEL_ID = "gemini-1.5-pro-002"
# ---------------------

print("--- Running Final Vertex AI Test ---")
print(f"Project: {PROJECT_ID}")
print(f"Location: {LOCATION}")
print(f"Model ID: {MODEL_ID}")
print("------------------------------------\n")

try:
    # Load credentials explicitly
    creds = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)

    # Initialize Vertex AI with the correct settings
    vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=creds)

    # Load the Gemini 1.5 Pro model
    model = GenerativeModel(MODEL_ID)

    # Define your preferred generation settings
    generation_config = GenerationConfig(
        temperature=0.6,
        top_p=0.95,
        max_output_tokens=1024,
    )

    # Define your preferred safety settings
    safety_settings = [
        SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_NONE),
        SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_NONE),
        SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_NONE),
        SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_NONE),
    ]

    # Make the API call
    response = model.generate_content(
        "Summarize the case United States v. Trump.",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )

    # Print the successful response
    print("\n--- ✅ SUCCESS! Gemini 1.5 Pro Output --- \n")
    print(response.text.strip())

except Exception as e:
    print("\n--- ❌ FAILED ---")
    print("\nAn unexpected error occurred:")
    print(e)
    print("\nIf this failed after the API toggle, the final step is to contact Google Support.")
