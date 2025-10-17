r"""
Video/Audio transcription with SRT timecodes using Gemini API.
Generates proper SRT subtitle format with timestamps.
Supports: MP4, M4A, MP3, WAV, AAC video/audio files

Usage:
    python video_transcript_srt.py [media_file]
    
Examples:
    python video_transcript_srt.py
    python video_transcript_srt.py U:\videos\interview.mp4
    python video_transcript_srt.py U:\audio\recording.m4a
    python video_transcript_srt.py "C:\My Videos\celebrity_news.mp4"
"""
import google.generativeai as genai
import json
import time
import os
import re
import sys

# --- CONFIG ---
API_KEY = "AIzaSyCOAZNg5SPfOyGTVLumnitWxAthWL8KO7s"
genai.configure(api_key=API_KEY)

# Default video path
DEFAULT_VIDEO_PATH = r"U:\docketwatch\output_part_00.mp4"
MODEL_NAME = "gemini-2.0-flash-exp"

# --- PROMPTS ---
SRT_TRANSCRIPT_PROMPT = """
Please provide a complete, accurate transcription of all spoken words in this video in SRT subtitle format.

SRT FORMAT REQUIREMENTS:
1. Number each subtitle sequentially (1, 2, 3, etc.)
2. Include precise timecodes in format: HH:MM:SS,mmm --> HH:MM:SS,mmm
3. Keep subtitle text concise (max 2 lines, ~42 characters per line)
4. Break at natural speech pauses
5. Use proper punctuation and capitalization

EXAMPLE FORMAT:
1
00:00:00,000 --> 00:00:03,500
Welcome to Call Her Daddy.
Today we have a very special guest.

2
00:00:03,500 --> 00:00:06,200
I'm so excited to introduce Kim Kardashian.

3
00:00:06,200 --> 00:00:09,100
Thank you so much for having me.
I don't usually do unscripted interviews.

IMPORTANT:
- Provide ONLY the SRT formatted transcript
- Include ALL spoken dialogue
- Use accurate timecodes based on when words are spoken
- Don't include any explanatory text or commentary
- Use [Music] or [Applause] for non-speech audio if relevant

Begin transcription:
"""


def upload_and_wait(video_path):
    """Upload video/audio file and wait for processing."""
    print(f"📤 Uploading: {os.path.basename(video_path)}")
    print(f"   Size: {os.path.getsize(video_path) / (1024*1024):.2f} MB")
    
    # Detect file type
    ext = os.path.splitext(video_path)[1].lower()
    if ext in ['.m4a', '.mp3', '.wav', '.aac']:
        mime_type = f"audio/{ext[1:]}" if ext != '.m4a' else "audio/mp4"
        file_type = "audio"
    else:
        mime_type = "video/mp4"
        file_type = "video"
    
    print(f"   Detected: {file_type.upper()} file ({mime_type})")
    
    try:
        # Upload the file
        video_file = genai.upload_file(
            path=video_path,
            display_name=os.path.basename(video_path)
        )
        print(f"✓ File uploaded: {video_file.name}")
        print(f"  State: {video_file.state.name}")
        
        # Wait for processing to complete
        while video_file.state.name == "PROCESSING":
            print(f"  Waiting for {file_type} processing...")
            time.sleep(5)
            video_file = genai.get_file(video_file.name)
        
        if video_file.state.name == "FAILED":
            raise ValueError(f"File processing failed: {video_file.state.name}")
        
        print(f"✓ File ready: {video_file.state.name}\n")
        return video_file

    except Exception as upload_error:
        print(f"❌ Upload failed: {upload_error}")
        print(f"\nTrying alternative approach with inline {file_type} data...")
        
        # Alternative: Use inline_data format (proper structure for API)
        import base64
        with open(video_path, 'rb') as f:
            file_bytes = f.read()
        
        video_file = {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(file_bytes).decode('utf-8')
            }
        }
        print(f"✓ File loaded via inline method ({len(file_bytes) / (1024*1024):.2f} MB)\n")
        return video_file


def get_srt_transcript(model, video_file):
    """Generate SRT format transcript with timecodes."""
    print("📝 Generating SRT transcript with timecodes...")
    response = model.generate_content(
        [SRT_TRANSCRIPT_PROMPT, video_file],
        request_options={"timeout": 600}
    )
    return response.text


def validate_srt(srt_text):
    """Basic validation of SRT format."""
    lines = srt_text.strip().split('\n')
    
    # Check for basic SRT structure
    has_numbers = any(line.strip().isdigit() for line in lines)
    has_timecodes = any('-->' in line for line in lines)
    
    if not has_numbers or not has_timecodes:
        print("⚠️  Warning: Output may not be in proper SRT format")
        return False
    
    return True


def main():
    """Main execution."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = DEFAULT_VIDEO_PATH
    
    # Validate file exists
    if not os.path.exists(video_path):
        print("=" * 80)
        print("ERROR: Video file not found!")
        print("=" * 80)
        print(f"\nFile: {video_path}")
        print("\nUsage:")
        print(f"  python {os.path.basename(__file__)} [video_file]")
        print("\nExamples:")
        print(f"  python {os.path.basename(__file__)}")
        print(f"  python {os.path.basename(__file__)} U:\\videos\\interview.mp4")
        print(f'  python {os.path.basename(__file__)} "C:\\My Videos\\news.mp4"')
        return
    
    print("=" * 80)
    print("VIDEO/AUDIO TRANSCRIPTION - SRT Format with Timecodes")
    print("=" * 80)
    print(f"\nFile: {video_path}")
    print()
    
    try:
        # Upload video
        video_file = upload_and_wait(video_path)
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Get SRT transcript
        srt_result = get_srt_transcript(model, video_file)
        
        print("\n" + "=" * 80)
        print("SRT TRANSCRIPT (Preview - First 50 lines)")
        print("=" * 80)
        print()
        
        # Show preview
        preview_lines = srt_result.split('\n')[:50]
        print('\n'.join(preview_lines))
        
        if len(srt_result.split('\n')) > 50:
            print("\n... (truncated for display)")
        
        # Validate
        print("\n" + "-" * 80)
        is_valid = validate_srt(srt_result)
        if is_valid:
            print("✓ SRT format validated")
        
        # Count subtitles
        subtitle_count = len([line for line in srt_result.split('\n') if line.strip().isdigit()])
        print(f"✓ Total subtitles: {subtitle_count}")
        
        # Save to SRT file
        base_name = os.path.splitext(video_path)[0]
        srt_file = base_name + ".srt"
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_result)
        
        print(f"\n✓ SRT file saved: {srt_file}")
        
        # Also save full transcript (text only, no timecodes)
        txt_file = base_name + "_transcript.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            # Extract just the dialogue (skip numbers and timecodes)
            lines = srt_result.split('\n')
            dialogue_lines = []
            for line in lines:
                line = line.strip()
                # Skip empty lines, numbers, and timecode lines
                if line and not line.isdigit() and '-->' not in line:
                    dialogue_lines.append(line)
            
            f.write('\n'.join(dialogue_lines))
        
        print(f"✓ Text transcript saved: {txt_file}")
        
        print("\n" + "=" * 80)
        print("COMPLETE!")
        print("=" * 80)
        print(f"\nFiles created:")
        print(f"  • {srt_file} (SRT subtitles with timecodes)")
        print(f"  • {txt_file} (Plain text transcript)")
        print("\nYou can now:")
        print("  • Import the .srt file into video editing software")
        print("  • Use it for closed captions")
        print("  • Search/analyze the text transcript")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
