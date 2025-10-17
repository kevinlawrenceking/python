"""
Quick script to list available Gemini models.
"""
import google.generativeai as genai

API_KEY = "AIzaSyCOAZNg5SPfOyGTVLumnitWxAthWL8KO7s"
genai.configure(api_key=API_KEY)

print("Available Gemini Models:")
print("=" * 80)

for model in genai.list_models():
    print(f"\nModel: {model.name}")
    print(f"  Display Name: {model.display_name}")
    print(f"  Description: {model.description}")
    print(f"  Supported Methods: {model.supported_generation_methods}")
    print(f"  Video Support: {any('video' in str(method).lower() for method in model.supported_generation_methods)}")

print("\n" + "=" * 80)
print("\nLooking for video-capable models...")
print("=" * 80)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"✓ {model.name}")
