from vertexai.preview.generative_models import GenerativeModel
import vertexai

vertexai.init(project="tmz-docketwatch-prod", location="us-central1")

model = GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Summarize the case United States v. Trump.")
print(response.text)
