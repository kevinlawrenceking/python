
import os
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# --- Configuration ---
# Get your API key from an environment variable (recommended)
# Replace "YOUR_API_KEY_HERE" if you absolutely must hardcode for a quick test,
# but it's strongly discouraged for anything beyond a one-off run.
API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBFifwhmbta61-IPtgYCzEa7X_svoIzE5s")

# Choose your Gemini 1.5 model. 'flash' is generally faster and cheaper for simple tasks.
# 'pro' is more capable for complex tasks.
MODEL_NAME = "gemini-2.5-pro"
# MODEL_NAME = "gemini-1.5-pro" # Uncomment to test the Pro model

TEST_PROMPT = "Hello, Gemini! What's the capital of France?"

# --- Script Logic ---
def test_gemini_api():
    if API_KEY == "YOUR_API_KEY_HERE_IF_NOT_SET_AS_ENV_VAR" and not os.getenv("GOOGLE_API_KEY"):
        print("------------------------------------------------------------------")
        print("ERROR: API Key not configured!")
        print("Please set the GOOGLE_API_KEY environment variable, or replace")
        print("the placeholder in the script with your actual API key.")
        print("Get your API key from: https://aistudio.google.com/app/apikey")
        print("------------------------------------------------------------------")
        return

    try:
        # Configure the API with your key
        genai.configure(api_key=API_KEY)
        print(f"Attempting to connect to Gemini API using model: {MODEL_NAME}")
        print(f"Sending test prompt: '{TEST_PROMPT}'\n")

        # Initialize the GenerativeModel
        model = genai.GenerativeModel(MODEL_NAME)

        # Generate content
        response = model.generate_content(TEST_PROMPT)

        # Print the response text
        print("--- API Response (Success!) ---")
        print(response.text)
        print("\nGemini API appears to be working correctly!")

    except google_exceptions.InvalidArgument as e:
        print("\n--- API Test Failed (Invalid Argument) ---")
        print(f"Error: {e}")
        print("This usually means:")
        print("  - Your API key is invalid or has not been enabled for the Generative Language API.")
        print("  - The model name might be incorrect or not available in your region.")
        print("  - Check your API key on Google AI Studio.")
    except google_exceptions.ResourceExhausted as e:
        print("\n--- API Test Failed (Resource Exhausted) ---")
        print(f"Error: {e}")
        print("This usually means you've hit a rate limit or your quota has been exceeded.")
        print("Wait a bit and try again, or check your usage limits in Google Cloud Console.")
    except google_exceptions.FailedPrecondition as e:
        print("\n--- API Test Failed (Failed Precondition) ---")
        print(f"Error: {e}")
        print("This can sometimes indicate an issue with API key permissions or region access.")
    except google_exceptions.InternalServerError as e:
        print("\n--- API Test Failed (Internal Server Error) ---")
        print(f"Error: {e}")
        print("This indicates an issue on Google's side. Try again later.")
    except Exception as e:
        print("\n--- API Test Failed (Other Error) ---")
        print(f"An unexpected error occurred: {e}")
        print("Check your internet connection and API key.")

if __name__ == "__main__":
    test_gemini_api()