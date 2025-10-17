import google.generativeai as genai
import json
import time

# --- CONFIG ---
genai.configure(api_key="AIzaSyCOAZNg5SPfOyGTVLumnitWxAthWL8KO7s")
MODEL_NAME = "gemini-2.0-flash-exp"  # Updated to available model with video support
VIDEO_PATH = r"U:\docketwatch\output_part_00.mp4"

# --- PROMPT ---
PROMPT = """
You are summarizing TMZ video footage for editors.

Instructions:
1. Watch the full clip carefully.
2. Summarize what happens, focusing on who, what, where, and tone.
3. Avoid filler like "the video shows".
4. Output JSON with:
   {
     "short_summary": "...",
     "long_summary": "...",
     "key_people": [],
     "key_locations": [],
     "tone": "..."
   }
"""

# --- UPLOAD VIDEO FILE ---
print("Uploading video file...")
try:
    # Upload the file
    video_file = genai.upload_file(
        path=VIDEO_PATH,
        display_name="TMZ Video Clip"
    )
    print(f"✓ Video uploaded: {video_file.name}")
    print(f"  State: {video_file.state.name}")
    
    # Wait for processing to complete
    while video_file.state.name == "PROCESSING":
        print("  Waiting for video processing...")
        time.sleep(5)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        raise ValueError(f"Video processing failed: {video_file.state.name}")
    
    print(f"✓ Video ready: {video_file.state.name}")

except Exception as upload_error:
    print(f"❌ Upload failed: {upload_error}")
    print("\nTrying alternative approach with direct file reference...")
    
    # Alternative: Use File API directly
    import pathlib
    video_file = {
        "mime_type": "video/mp4",
        "data": pathlib.Path(VIDEO_PATH).read_bytes()
    }

# --- CALL GEMINI ---
print("\nGenerating summary...")
model = genai.GenerativeModel(MODEL_NAME)

response = model.generate_content(
    [PROMPT, video_file],
    request_options={"timeout": 600}
)

# --- OUTPUT ---
print(response.text)

# Optionally parse JSON if the model returns structured text
try:
    data = json.loads(response.text)
    print(json.dumps(data, indent=2))
except json.JSONDecodeError:
    print("Model returned non-JSON text.")