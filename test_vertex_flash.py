import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account

# Load service account JSON
SERVICE_ACCOUNT_PATH = r"U:\docketwatch\vertex\tmz-docketwatch-prod-3c1d09714a96.json"
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)

# Initialize Vertex AI with credentials object
vertexai.init(
    project="tmz-docketwatch-prod",
    location="us-central1",
    credentials=credentials
)

# Run test
model = GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Summarize the case United States v. Trump.")

print("\n=== Gemini Flash Response ===\n")
print(response.text)
