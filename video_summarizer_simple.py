"""
Simplified video summarization with Gemini API.
Uses the Files API correctly to avoid ragStoreName error.
"""
import google.generativeai as genai
import json
import time
import os

# --- CONFIG ---
API_KEY = "AIzaSyCOAZNg5SPfOyGTVLumnitWxAthWL8KO7s"
genai.configure(api_key=API_KEY)

VIDEO_PATH = r"U:\docketwatch\output_part_00.mp4"
MODEL_NAME = "gemini-2.0-flash-exp"  # Latest model with video support

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


def upload_and_wait(video_path):
    """Upload video file and wait for processing."""
    print(f"📤 Uploading: {os.path.basename(video_path)}")
    print(f"   Size: {os.path.getsize(video_path) / (1024*1024):.2f} MB")
    
    # Upload file (no ragStoreName needed with correct API usage)
    video_file = genai.upload_file(
        path=video_path,
        display_name=os.path.basename(video_path)
    )
    
    print(f"✓ Uploaded: {video_file.name}")
    print(f"  URI: {video_file.uri}")
    
    # Wait for processing
    print("⏳ Processing video...")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
        print(".", end="", flush=True)
    
    print()
    
    if video_file.state.name == "FAILED":
        raise ValueError(f"Video processing failed!")
    
    print(f"✓ Ready: {video_file.state.name}")
    return video_file


def summarize_video(video_path, prompt):
    """Summarize video using Gemini API."""
    
    # Upload and process video
    video_file = upload_and_wait(video_path)
    
    # Create model and generate
    model = genai.GenerativeModel(MODEL_NAME)
    
    print("\n🤖 Generating summary...")
    response = model.generate_content(
        [prompt, video_file],
        request_options={"timeout": 600}
    )
    
    return response.text


def main():
    """Main execution."""
    print("=" * 80)
    print("TMZ VIDEO SUMMARIZER - Gemini API")
    print("=" * 80)
    print()
    
    if not os.path.exists(VIDEO_PATH):
        print(f"❌ Error: Video file not found: {VIDEO_PATH}")
        return
    
    try:
        # Generate summary
        result = summarize_video(VIDEO_PATH, PROMPT)
        
        print("\n" + "=" * 80)
        print("SUMMARY RESULT")
        print("=" * 80)
        print()
        print(result)
        print()
        
        # Try to parse as JSON
        try:
            data = json.loads(result)
            print("\n" + "=" * 80)
            print("PARSED JSON")
            print("=" * 80)
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print("\n(Note: Response is not valid JSON)")
        
        print("\n✓ Complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
