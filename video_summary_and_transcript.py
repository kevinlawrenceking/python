"""
Video summarization + transcription with Gemini API.
Analyzes video content and provides full transcript.
"""
import google.generativeai as genai
import json
import time
import os

# --- CONFIG ---
API_KEY = "AIzaSyCOAZNg5SPfOyGTVLumnitWxAthWL8KO7s"
genai.configure(api_key=API_KEY)

VIDEO_PATH = r"U:\docketwatch\output_part_00.mp4"
MODEL_NAME = "gemini-2.0-flash-exp"

# --- PROMPTS ---
SUMMARY_PROMPT = """
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

TRANSCRIPT_PROMPT = """
Please provide a complete, accurate transcription of all spoken words in this video.

Format:
- Include speaker labels if you can identify different speakers (e.g., "Speaker 1:", "Reporter:")
- Use proper punctuation and capitalization
- Include [inaudible] for unclear sections
- Include [music] or [sound effects] for non-speech audio
- Separate different speakers/sections with line breaks

Provide only the transcript, no additional commentary.
"""


def upload_and_wait(video_path):
    """Upload video file and wait for processing."""
    print(f"📤 Uploading: {os.path.basename(video_path)}")
    print(f"   Size: {os.path.getsize(video_path) / (1024*1024):.2f} MB")
    
    video_file = genai.upload_file(
        path=video_path,
        display_name=os.path.basename(video_path)
    )
    
    print(f"✓ Uploaded: {video_file.name}")
    
    # Wait for processing
    print("⏳ Processing video", end="", flush=True)
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
        print(".", end="", flush=True)
    
    print()
    
    if video_file.state.name == "FAILED":
        raise ValueError(f"Video processing failed!")
    
    print(f"✓ Ready: {video_file.state.name}\n")
    return video_file


def get_summary(model, video_file):
    """Generate video summary."""
    print("🤖 Generating summary...")
    response = model.generate_content(
        [SUMMARY_PROMPT, video_file],
        request_options={"timeout": 600}
    )
    return response.text


def get_transcript(model, video_file):
    """Generate video transcript."""
    print("📝 Generating transcript...")
    response = model.generate_content(
        [TRANSCRIPT_PROMPT, video_file],
        request_options={"timeout": 600}
    )
    return response.text


def main():
    """Main execution."""
    print("=" * 80)
    print("TMZ VIDEO ANALYZER - Summary + Transcript")
    print("=" * 80)
    print()
    
    if not os.path.exists(VIDEO_PATH):
        print(f"❌ Error: Video file not found: {VIDEO_PATH}")
        return
    
    try:
        # Upload video once
        video_file = upload_and_wait(VIDEO_PATH)
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Get summary
        summary_result = get_summary(model, video_file)
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()
        
        # Try to parse as JSON
        try:
            summary_data = json.loads(summary_result)
            print(json.dumps(summary_data, indent=2))
        except json.JSONDecodeError:
            print(summary_result)
        
        # Get transcript
        print("\n")
        transcript_result = get_transcript(model, video_file)
        
        print("\n" + "=" * 80)
        print("TRANSCRIPT")
        print("=" * 80)
        print()
        print(transcript_result)
        
        # Save to file
        output_file = VIDEO_PATH.replace(".mp4", "_analysis.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("VIDEO ANALYSIS\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("SUMMARY\n")
            f.write("-" * 80 + "\n")
            try:
                f.write(json.dumps(json.loads(summary_result), indent=2))
            except:
                f.write(summary_result)
            
            f.write("\n\n")
            f.write("TRANSCRIPT\n")
            f.write("-" * 80 + "\n")
            f.write(transcript_result)
        
        print("\n" + "=" * 80)
        print(f"✓ Complete! Saved to: {output_file}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
