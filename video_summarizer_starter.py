"""
Video Asset Summarizer using Google Gemini API
Starter template with base functions for video processing and AI summarization
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# Google Vertex AI imports
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting, GenerationConfig

# Video processing imports (install with: pip install opencv-python moviepy pillow)
import cv2
from moviepy.editor import VideoFileClip
from PIL import Image
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_summarizer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# GEMINI API CONFIGURATION
# ============================================================================

# Service account path - adjust to your project location
SCRIPT_DIR = Path(__file__).parent.absolute()
SERVICE_ACCOUNT_FILE = SCRIPT_DIR / "docketwatch-service-account.json"

# Vertex AI project details
PROJECT_ID = "docketwatch"  # Your GCP project ID
LOCATION = "us-central1"    # GCP region
MODEL_NAME = "gemini-2.5-flash"  # Or gemini-1.5-pro, gemini-1.5-flash

# Safety settings - adjust based on your content
SAFETY_SETTINGS = [
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
]


def initialize_vertex_ai():
    """Initialize Vertex AI with service account credentials."""
    try:
        if not SERVICE_ACCOUNT_FILE.exists():
            raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        
        # Set environment variable for authentication
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(SERVICE_ACCOUNT_FILE)
        
        # Initialize Vertex AI
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        logger.info(f"Vertex AI initialized: Project={PROJECT_ID}, Location={LOCATION}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        return False


def call_gemini_api(prompt, max_tokens=8192, temperature=0.2, image_data=None, video_data=None):
    """
    Call Gemini API with text, image, or video content.
    
    Args:
        prompt: Text prompt/question
        max_tokens: Maximum output tokens
        temperature: Creativity (0.0-1.0)
        image_data: PIL Image object or bytes
        video_data: Video file bytes or Part object
        
    Returns:
        str: Model response text or None on error
    """
    try:
        model = GenerativeModel(MODEL_NAME)
        
        # Build content parts
        contents = []
        
        # Add video if provided
        if video_data:
            if isinstance(video_data, Part):
                contents.append(video_data)
            else:
                # Assume bytes
                video_part = Part.from_data(data=video_data, mime_type="video/mp4")
                contents.append(video_part)
        
        # Add image if provided
        if image_data:
            if isinstance(image_data, Image.Image):
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                image_data.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()
                image_part = Part.from_data(data=img_bytes, mime_type="image/jpeg")
            else:
                # Assume bytes
                image_part = Part.from_data(data=image_data, mime_type="image/jpeg")
            contents.append(image_part)
        
        # Add text prompt
        contents.append(prompt)
        
        # Generation config
        config = GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
            top_k=40
        )
        
        # Generate response
        response = model.generate_content(
            contents,
            generation_config=config,
            safety_settings=SAFETY_SETTINGS,
            stream=False
        )
        
        # Handle response
        if not response or not response.candidates:
            logger.error("No response from Gemini API")
            return None
        
        candidate = response.candidates[0]
        
        # Check finish reason
        finish_reason = candidate.finish_reason
        if finish_reason == 1:  # STOP - normal completion
            return candidate.content.parts[0].text
        elif finish_reason == 2:  # MAX_TOKENS
            logger.warning("Response truncated due to token limit")
            if candidate.content and candidate.content.parts:
                return candidate.content.parts[0].text
            return None
        elif finish_reason == 3:  # SAFETY
            logger.error("Response blocked by safety filters")
            return None
        elif finish_reason == 4:  # RECITATION
            logger.error("Response blocked due to recitation")
            return None
        else:
            logger.error(f"Unknown finish reason: {finish_reason}")
            return None
            
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return None


# ============================================================================
# VIDEO PROCESSING FUNCTIONS
# ============================================================================

def extract_video_metadata(video_path):
    """
    Extract basic metadata from video file.
    
    Returns:
        dict: Metadata including duration, fps, resolution, codec, etc.
    """
    try:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        # Use moviepy for high-level info
        clip = VideoFileClip(str(video_path))
        
        # Use opencv for additional details
        cap = cv2.VideoCapture(str(video_path))
        
        metadata = {
            'filename': video_path.name,
            'filepath': str(video_path),
            'filesize_mb': video_path.stat().st_size / (1024 * 1024),
            'duration_seconds': clip.duration,
            'fps': clip.fps,
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'codec': int(cap.get(cv2.CAP_PROP_FOURCC)),
            'has_audio': clip.audio is not None
        }
        
        clip.close()
        cap.release()
        
        logger.info(f"Extracted metadata: {metadata['filename']} - "
                   f"{metadata['duration_seconds']:.1f}s @ {metadata['fps']:.1f}fps")
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract metadata: {e}")
        return None


def extract_frames(video_path, num_frames=10, method='uniform'):
    """
    Extract frames from video for analysis.
    
    Args:
        video_path: Path to video file
        num_frames: Number of frames to extract
        method: 'uniform' (evenly spaced) or 'keyframes' (scene changes)
        
    Returns:
        list: List of PIL Image objects
    """
    try:
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        
        if method == 'uniform':
            # Extract evenly spaced frames
            frame_indices = [int(i * total_frames / num_frames) for i in range(num_frames)]
            
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    frames.append(pil_image)
        
        elif method == 'keyframes':
            # TODO: Implement scene detection for keyframes
            # For now, fall back to uniform
            logger.warning("Keyframe detection not implemented, using uniform sampling")
            return extract_frames(video_path, num_frames, method='uniform')
        
        cap.release()
        logger.info(f"Extracted {len(frames)} frames from {video_path.name}")
        return frames
        
    except Exception as e:
        logger.error(f"Failed to extract frames: {e}")
        return []


def create_video_thumbnail(video_path, timestamp=None, output_path=None):
    """
    Create a thumbnail image from video.
    
    Args:
        video_path: Path to video file
        timestamp: Time in seconds (None = middle of video)
        output_path: Where to save thumbnail (None = return PIL Image)
        
    Returns:
        PIL.Image or str: Image object or path to saved thumbnail
    """
    try:
        clip = VideoFileClip(str(video_path))
        
        if timestamp is None:
            timestamp = clip.duration / 2  # Middle of video
        
        # Get frame at timestamp
        frame = clip.get_frame(timestamp)
        pil_image = Image.fromarray(frame)
        
        if output_path:
            pil_image.save(output_path)
            logger.info(f"Thumbnail saved: {output_path}")
            clip.close()
            return output_path
        else:
            clip.close()
            return pil_image
            
    except Exception as e:
        logger.error(f"Failed to create thumbnail: {e}")
        return None


def extract_audio(video_path, output_path=None):
    """
    Extract audio track from video.
    
    Args:
        video_path: Path to video file
        output_path: Where to save audio (None = auto-generate)
        
    Returns:
        str: Path to extracted audio file
    """
    try:
        video_path = Path(video_path)
        
        if output_path is None:
            output_path = video_path.with_suffix('.mp3')
        
        clip = VideoFileClip(str(video_path))
        
        if clip.audio is None:
            logger.warning(f"No audio track found in {video_path.name}")
            clip.close()
            return None
        
        clip.audio.write_audiofile(str(output_path), logger=None)
        clip.close()
        
        logger.info(f"Audio extracted: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Failed to extract audio: {e}")
        return None


# ============================================================================
# VIDEO SUMMARIZATION FUNCTIONS
# ============================================================================

def summarize_video_with_frames(video_path, num_frames=5):
    """
    Summarize video by analyzing extracted frames.
    
    Args:
        video_path: Path to video file
        num_frames: Number of frames to analyze
        
    Returns:
        dict: Summary results
    """
    try:
        # Extract metadata
        metadata = extract_video_metadata(video_path)
        if not metadata:
            return None
        
        # Extract frames
        frames = extract_frames(video_path, num_frames=num_frames)
        if not frames:
            return None
        
        # Build prompt
        prompt = f"""Analyze this video based on {len(frames)} frames extracted from a {metadata['duration_seconds']:.1f} second video.

Please provide:
1. **Content Summary**: What is happening in this video?
2. **Key Scenes**: Describe the main scenes or events
3. **Visual Elements**: Notable objects, people, text, or graphics
4. **Context**: Inferred setting, time of day, location type
5. **Action/Motion**: Types of movement or activity detected

Format as structured sections with clear headings."""
        
        # Analyze each frame with Gemini
        frame_analyses = []
        for i, frame in enumerate(frames):
            logger.info(f"Analyzing frame {i+1}/{len(frames)}...")
            
            frame_prompt = f"Frame {i+1} of {len(frames)} - Describe what you see in detail:"
            response = call_gemini_api(frame_prompt, image_data=frame, max_tokens=1024)
            
            if response:
                frame_analyses.append({
                    'frame_number': i+1,
                    'timestamp': (i * metadata['duration_seconds'] / num_frames),
                    'description': response
                })
            
            # Rate limiting
            time.sleep(0.5)
        
        # Create comprehensive summary from all frames
        combined_prompt = f"""Based on these {len(frame_analyses)} frame descriptions from a video, create a comprehensive summary:

{chr(10).join([f"Frame {a['frame_number']} ({a['timestamp']:.1f}s): {a['description']}" for a in frame_analyses])}

{prompt}"""
        
        summary = call_gemini_api(combined_prompt, max_tokens=4096)
        
        return {
            'metadata': metadata,
            'frame_count_analyzed': len(frames),
            'frame_analyses': frame_analyses,
            'comprehensive_summary': summary,
            'analyzed_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to summarize video: {e}")
        return None


def summarize_video_direct(video_path):
    """
    Send entire video to Gemini for direct analysis (Gemini 1.5+ supports video).
    
    Args:
        video_path: Path to video file
        
    Returns:
        dict: Summary results
    """
    try:
        # Extract metadata first
        metadata = extract_video_metadata(video_path)
        if not metadata:
            return None
        
        # Check file size (Gemini has limits)
        if metadata['filesize_mb'] > 100:
            logger.warning(f"Video too large ({metadata['filesize_mb']:.1f}MB), use frame-based analysis instead")
            return None
        
        # Read video file
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
        
        # Build prompt
        prompt = """Analyze this entire video and provide:

1. **Overall Summary**: What is this video about?
2. **Timeline of Events**: Key moments in chronological order
3. **Visual Content**: Objects, people, text, graphics shown
4. **Audio Content**: Spoken words, sounds, music (if any)
5. **Setting & Context**: Location, time of day, environment
6. **Actions & Activities**: What happens in the video
7. **Notable Elements**: Anything remarkable or important

Be thorough and detailed."""
        
        # Send to Gemini
        logger.info(f"Sending video to Gemini API ({metadata['filesize_mb']:.1f}MB)...")
        summary = call_gemini_api(prompt, video_data=video_bytes, max_tokens=8192)
        
        return {
            'metadata': metadata,
            'method': 'direct_video_analysis',
            'summary': summary,
            'analyzed_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to summarize video directly: {e}")
        return None


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Example usage of video summarization."""
    
    # Initialize Gemini API
    if not initialize_vertex_ai():
        logger.error("Failed to initialize Vertex AI - check service account file")
        return
    
    # Example video path
    video_path = "sample_video.mp4"  # Replace with your video
    
    if not Path(video_path).exists():
        logger.error(f"Video not found: {video_path}")
        return
    
    # Method 1: Frame-based analysis (works for any video size)
    logger.info("=" * 60)
    logger.info("METHOD 1: Frame-based Analysis")
    logger.info("=" * 60)
    result = summarize_video_with_frames(video_path, num_frames=8)
    
    if result:
        print("\n" + "=" * 60)
        print("VIDEO SUMMARY (Frame-based)")
        print("=" * 60)
        print(f"\nFile: {result['metadata']['filename']}")
        print(f"Duration: {result['metadata']['duration_seconds']:.1f}s")
        print(f"Resolution: {result['metadata']['width']}x{result['metadata']['height']}")
        print(f"\n{result['comprehensive_summary']}")
        
        # Save results
        output_file = f"summary_{Path(video_path).stem}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    
    # Method 2: Direct video analysis (only for smaller videos)
    logger.info("\n" + "=" * 60)
    logger.info("METHOD 2: Direct Video Analysis")
    logger.info("=" * 60)
    result2 = summarize_video_direct(video_path)
    
    if result2:
        print("\n" + "=" * 60)
        print("VIDEO SUMMARY (Direct)")
        print("=" * 60)
        print(f"\n{result2['summary']}")


if __name__ == "__main__":
    main()
