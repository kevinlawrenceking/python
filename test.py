import os
import vertexai
from vertexai.generative_models import GenerativeModel

# Set path to your service account key
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"U:\docketwatch\vertex\tmz-docketwatch-prod-3c1d09714a96.json"

# Initialize Vertex AI with your project and region
vertexai.init(project="tmz-docketwatch-prod", location="us-central1")

# Load Gemini 1.5 Pro model (new method)
model = GenerativeModel("gemini-1.5-pro")

# Run test prompt
response = model.generate_content("Summarize the case United States v. Trump.")

# Print output
print(response.text)
