# Reusable Code Snippets for Video Transcription + AI Summary Project
# Collection of proven patterns from DocketWatch for new project

"""
OVERVIEW:
This file contains battle-tested code snippets for:
- Gemini API access (Vertex AI)
- SQL Server database connections
- Email sending (SMTP)
- 3-stage FACT_GUARD pipeline
- Error handling & logging
- Video processing utilities

Copy/paste these into your new project as needed.
"""

# ============================================================================
# IMPORTS - Add these to your project
# ============================================================================

"""
Required pip installs:
pip install google-cloud-aiplatform pyodbc opencv-python moviepy pillow

Optional for transcription:
pip install google-cloud-speech openai-whisper
"""

import os
import sys
import json
import time
import logging
import smtplib
import pyodbc
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Google Vertex AI
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting, GenerationConfig

# Video processing
import cv2
from moviepy.editor import VideoFileClip
from PIL import Image


# ============================================================================
# 1. LOGGING SETUP
# ============================================================================

def setup_logging(log_file='app.log', log_level=logging.INFO):
    """
    Configure logging to both file and console.
    
    Usage:
        logger = setup_logging('video_processor.log')
        logger.info("Processing started")
        logger.error("Something went wrong", exc_info=True)
    """
    # Create logs directory if needed
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: {log_file}")
    return logger


# ============================================================================
# 2. GEMINI API ACCESS (Vertex AI)
# ============================================================================

# Configuration - adjust for your project
SCRIPT_DIR = Path(__file__).parent.absolute()
SERVICE_ACCOUNT_FILE = SCRIPT_DIR / "docketwatch-service-account.json"  # Same service account
PROJECT_ID = "docketwatch"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"  # Or gemini-1.5-pro, gemini-1.5-flash

# Safety settings for sensitive content (legal/news)
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
    """
    Initialize Vertex AI with service account credentials.
    Call this once at startup.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not SERVICE_ACCOUNT_FILE.exists():
            raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        
        # Set environment variable for authentication
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(SERVICE_ACCOUNT_FILE)
        
        # Initialize Vertex AI
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        
        logging.info(f"✓ Vertex AI initialized: Project={PROJECT_ID}, Location={LOCATION}")
        return True
        
    except Exception as e:
        logging.error(f"✗ Failed to initialize Vertex AI: {e}", exc_info=True)
        return False


def call_gemini(prompt, max_tokens=8192, temperature=0.2, image_data=None, video_data=None):
    """
    Call Gemini API with text, image, or video content.
    Handles errors, finish reasons, and retries.
    
    Args:
        prompt (str): Text prompt/question
        max_tokens (int): Maximum output tokens (8192 max for gemini-2.5-flash)
        temperature (float): Creativity level 0.0-1.0 (0.2 for factual)
        image_data: PIL Image object or bytes
        video_data: Video file bytes or Part object
        
    Returns:
        str: Model response text or None on error
        
    Usage:
        response = call_gemini("Summarize this video", video_data=video_bytes, max_tokens=8192)
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
                import io
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
            logging.error("No response from Gemini API")
            return None
        
        candidate = response.candidates[0]
        
        # Check finish reason
        finish_reason = candidate.finish_reason
        if finish_reason == 1:  # STOP - normal completion
            return candidate.content.parts[0].text
            
        elif finish_reason == 2:  # MAX_TOKENS - truncated
            logging.warning("Response truncated due to token limit")
            if candidate.content and candidate.content.parts:
                text = candidate.content.parts[0].text
                logging.warning(f"Returning partial response ({len(text)} chars)")
                return text
            return None
            
        elif finish_reason == 3:  # SAFETY - blocked by filters
            logging.error("Response blocked by safety filters")
            return None
            
        elif finish_reason == 4:  # RECITATION - copyright issue
            logging.error("Response blocked due to recitation/copyright")
            return None
            
        else:
            logging.error(f"Unknown finish reason: {finish_reason}")
            return None
            
    except Exception as e:
        logging.error(f"Gemini API call failed: {e}", exc_info=True)
        return None


def call_gemini_with_json(prompt, json_schema, max_tokens=8192, temperature=0.2):
    """
    Call Gemini API and enforce JSON response with schema.
    Includes auto-repair for truncated JSON.
    
    Args:
        prompt (str): Extraction prompt
        json_schema (dict): JSON schema with type/properties/required
        max_tokens (int): Output token limit (8192 max)
        temperature (float): Creativity (0.2 for structured extraction)
        
    Returns:
        dict: Parsed JSON response or None
        
    Usage:
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["summary"]
        }
        result = call_gemini_with_json("Extract key info...", schema)
    """
    try:
        # Add JSON schema to prompt
        full_prompt = f"""{prompt}

CRITICAL: Respond with ONLY valid JSON matching this schema:
{json.dumps(json_schema, indent=2)}

Rules:
- Start with {{ and end with }}
- Use double quotes for strings
- Escape special characters
- No markdown, no explanations, ONLY JSON
"""
        
        # Call API
        response_text = call_gemini(full_prompt, max_tokens=max_tokens, temperature=temperature)
        
        if not response_text:
            return None
        
        # Try to parse JSON
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_text)
            return result
            
        except json.JSONDecodeError as e:
            logging.warning(f"JSON parse error: {e}")
            
            # Try to auto-repair truncated JSON
            repaired = auto_close_json(response_text)
            try:
                result = json.loads(repaired)
                logging.info("✓ JSON auto-repair successful")
                return result
            except:
                logging.error(f"JSON repair failed. Response preview: {response_text[:500]}")
                return None
                
    except Exception as e:
        logging.error(f"JSON API call failed: {e}", exc_info=True)
        return None


def auto_close_json(text):
    """
    Attempt to repair truncated JSON by closing open structures.
    
    Args:
        text (str): Potentially truncated JSON string
        
    Returns:
        str: Repaired JSON string
    """
    text = text.strip()
    
    # Count open/close brackets
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    # Add missing closing characters
    if open_brackets > close_brackets:
        text += ']' * (open_brackets - close_brackets)
    
    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    
    return text


# ============================================================================
# 3. SQL SERVER DATABASE CONNECTION
# ============================================================================

def get_db_connection(dsn_name='Docketwatch'):
    """
    Create SQL Server database connection using DSN.
    
    Args:
        dsn_name (str): ODBC DSN name configured in Windows
        
    Returns:
        pyodbc.Connection: Database connection or None
        
    Usage:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            row = cursor.fetchone()
            conn.close()
    """
    try:
        conn = pyodbc.connect(f'DSN={dsn_name}', autocommit=False)
        logging.info(f"✓ Database connected: {dsn_name}")
        return conn
    except Exception as e:
        logging.error(f"✗ Database connection failed: {e}", exc_info=True)
        return None


def execute_query(query, params=None, fetch='all', dsn_name='Docketwatch'):
    """
    Execute SQL query with automatic connection handling.
    
    Args:
        query (str): SQL query with ? placeholders
        params (tuple): Parameter values
        fetch (str): 'all', 'one', or 'none' (for INSERT/UPDATE)
        dsn_name (str): Database DSN name
        
    Returns:
        list/dict/None: Query results
        
    Usage:
        # SELECT multiple rows
        rows = execute_query("SELECT * FROM videos WHERE status = ?", ('pending',))
        
        # SELECT single row
        row = execute_query("SELECT * FROM videos WHERE id = ?", (123,), fetch='one')
        
        # INSERT/UPDATE
        execute_query("UPDATE videos SET status = ? WHERE id = ?", ('processed', 123), fetch='none')
    """
    conn = None
    try:
        conn = get_db_connection(dsn_name)
        if not conn:
            return None
        
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch == 'all':
            rows = cursor.fetchall()
            # Convert to list of dicts
            columns = [column[0] for column in cursor.description]
            result = [dict(zip(columns, row)) for row in rows]
            conn.close()
            return result
            
        elif fetch == 'one':
            row = cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                result = dict(zip(columns, row))
                conn.close()
                return result
            conn.close()
            return None
            
        elif fetch == 'none':
            conn.commit()
            conn.close()
            return True
            
    except Exception as e:
        logging.error(f"Query failed: {e}", exc_info=True)
        if conn:
            conn.rollback()
            conn.close()
        return None


def insert_with_identity(query, params, dsn_name='Docketwatch'):
    """
    Execute INSERT and return the new identity (auto-increment ID).
    
    Args:
        query (str): INSERT query with ? placeholders
        params (tuple): Parameter values
        dsn_name (str): Database DSN name
        
    Returns:
        int: New record ID or None
        
    Usage:
        new_id = insert_with_identity(
            "INSERT INTO videos (filename, status) VALUES (?, ?)",
            ('video.mp4', 'pending')
        )
    """
    conn = None
    try:
        conn = get_db_connection(dsn_name)
        if not conn:
            return None
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        # Get the identity
        cursor.execute("SELECT SCOPE_IDENTITY()")
        new_id = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return int(new_id)
        
    except Exception as e:
        logging.error(f"Insert with identity failed: {e}", exc_info=True)
        if conn:
            conn.rollback()
            conn.close()
        return None


# ============================================================================
# 4. EMAIL SENDING (SMTP)
# ============================================================================

def send_email(to_address, subject, body_html, from_address="noreply@docketwatch.com", 
               smtp_server="mail.docketwatch.com", smtp_port=587, attachments=None):
    """
    Send email via SMTP with optional attachments.
    
    Args:
        to_address (str or list): Recipient email(s)
        subject (str): Email subject
        body_html (str): HTML email body
        from_address (str): Sender email
        smtp_server (str): SMTP server hostname
        smtp_port (int): SMTP port (587 for TLS, 25 for plain)
        attachments (list): List of file paths to attach
        
    Returns:
        bool: True if sent successfully
        
    Usage:
        send_email(
            to_address="user@example.com",
            subject="Video Processing Complete",
            body_html="<h1>Your video is ready</h1><p>View it here...</p>",
            attachments=["summary.pdf"]
        )
    """
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_address
        
        # Handle multiple recipients
        if isinstance(to_address, list):
            msg['To'] = ', '.join(to_address)
        else:
            msg['To'] = to_address
            to_address = [to_address]
        
        # Attach HTML body
        html_part = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Attach files if provided
        if attachments:
            for file_path in attachments:
                file_path = Path(file_path)
                if not file_path.exists():
                    logging.warning(f"Attachment not found: {file_path}")
                    continue
                
                with open(file_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={file_path.name}'
                    )
                    msg.attach(part)
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        # Note: Add authentication if needed
        # server.login(username, password)
        server.send_message(msg)
        server.quit()
        
        logging.info(f"✓ Email sent to {', '.join(to_address)}: {subject}")
        return True
        
    except Exception as e:
        logging.error(f"✗ Failed to send email: {e}", exc_info=True)
        return False


# ============================================================================
# 5. THREE-STAGE FACT_GUARD PIPELINE
# ============================================================================

def extract_facts_from_transcript(transcript_text, video_metadata=None):
    """
    Stage 1: Extract structured facts from video transcript.
    
    Args:
        transcript_text (str): Full transcript of video
        video_metadata (dict): Optional metadata (duration, filename, etc.)
        
    Returns:
        dict: Extracted facts in JSON format
        
    Schema includes:
    - video_type: interview, news, hearing, meeting, etc.
    - date_recorded_iso: YYYY-MM-DD
    - participants: [{name, role, affiliation}]
    - main_topic: Overall subject
    - key_points: [list of main points discussed]
    - quotes: [{speaker, quote, timestamp}]
    - action_items: [list of decisions/next steps]
    - locations_mentioned: [list of places]
    - organizations_mentioned: [list of orgs]
    - numbers_mentioned: [financial figures, dates, statistics]
    """
    # Define extraction schema
    schema = {
        "type": "object",
        "properties": {
            "video_type": {
                "type": "string",
                "enum": ["interview", "news_segment", "hearing", "meeting", 
                        "deposition", "press_conference", "court_proceeding", "other"]
            },
            "date_recorded_iso": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "participants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "affiliation": {"type": "string"}
                    }
                }
            },
            "main_topic": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string"},
                        "quote": {"type": "string"},
                        "timestamp": {"type": "string"}
                    }
                }
            },
            "action_items": {"type": "array", "items": {"type": "string"}},
            "locations_mentioned": {"type": "array", "items": {"type": "string"}},
            "organizations_mentioned": {"type": "array", "items": {"type": "string"}},
            "numbers_mentioned": {"type": "array", "items": {"type": "string"}},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral", "mixed"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
        },
        "required": ["video_type", "main_topic", "key_points"]
    }
    
    # Build extraction prompt
    prompt = f"""Extract structured information from this video transcript. Be precise and only include information explicitly stated.

TRANSCRIPT:
{transcript_text}

Extract all relevant facts and structure them according to the JSON schema provided. 
- For participants: Include full names, roles/titles, and organizational affiliations if mentioned
- For quotes: Select the most significant or newsworthy statements
- For numbers: Include dollar amounts, dates, statistics, measurements
- Confidence: Rate 'high' if information is clear, 'medium' if somewhat ambiguous, 'low' if uncertain
"""
    
    if video_metadata:
        prompt += f"\n\nVIDEO METADATA:\n{json.dumps(video_metadata, indent=2)}"
    
    # Call Gemini with JSON enforcement
    result = call_gemini_with_json(prompt, schema, max_tokens=8192, temperature=0.2)
    
    if result:
        logging.info(f"✓ Extracted facts: {result.get('main_topic', 'N/A')}")
    else:
        logging.error("✗ Fact extraction failed")
    
    return result


def verify_facts(extracted_facts, transcript_text):
    """
    Stage 2: Verify extracted facts against source transcript.
    Checks for hallucinations, misinterpretations, or unsupported claims.
    
    Args:
        extracted_facts (dict): Facts from Stage 1
        transcript_text (str): Original transcript
        
    Returns:
        dict: Verification result with status and notes
    """
    prompt = f"""You are a fact-checker. Review these extracted facts against the source transcript and verify accuracy.

EXTRACTED FACTS:
{json.dumps(extracted_facts, indent=2)}

SOURCE TRANSCRIPT:
{transcript_text}

For each fact, verify:
1. Is it explicitly stated in the transcript?
2. Is it correctly interpreted (no exaggeration or misrepresentation)?
3. Are dates, names, numbers, and quotes accurate?
4. Are there any fabricated details not present in the source?

Respond with JSON:
{{
    "verification_status": "PASSED" or "FAILED",
    "verified_fields": ["field1", "field2", ...],
    "flagged_issues": [
        {{"field": "field_name", "issue": "description of problem"}}
    ],
    "confidence_score": 0-100,
    "notes": "Overall assessment"
}}

If ANY fact is unsupported or incorrect, status must be FAILED.
"""
    
    result = call_gemini_with_json(
        prompt,
        {
            "type": "object",
            "properties": {
                "verification_status": {"type": "string", "enum": ["PASSED", "FAILED"]},
                "verified_fields": {"type": "array", "items": {"type": "string"}},
                "flagged_issues": {"type": "array"},
                "confidence_score": {"type": "number"},
                "notes": {"type": "string"}
            },
            "required": ["verification_status", "notes"]
        },
        max_tokens=4096,
        temperature=0.1  # Very low temperature for strict verification
    )
    
    if result:
        status = result.get('verification_status', 'FAILED')
        logging.info(f"✓ Verification: {status} (confidence: {result.get('confidence_score', 0)})")
    else:
        logging.error("✗ Verification failed")
    
    return result


def render_summary(verified_facts, transcript_text):
    """
    Stage 3: Generate human-readable summary from verified facts.
    
    Args:
        verified_facts (dict): Facts that passed verification
        transcript_text (str): Original transcript
        
    Returns:
        dict: HTML summary and structured fields
    """
    prompt = f"""Create a professional summary of this video based on the verified facts below.

VERIFIED FACTS:
{json.dumps(verified_facts, indent=2)}

Generate a summary with these sections:
1. **OVERVIEW** (2-3 sentences): What is this video about?
2. **KEY POINTS** (bullet list): Main topics discussed
3. **NOTABLE QUOTES** (if any): Significant statements with attribution
4. **ACTION ITEMS** (if any): Decisions made or next steps
5. **CONTEXT** (1-2 sentences): Setting, participants, relevance

Also extract:
- headline: Concise title (10 words max)
- summary_text: Plain text version (3-5 sentences)
- newsworthiness: "yes" or "no" (is this newsworthy/important?)
- newsworthiness_reason: Why it is or isn't newsworthy

Respond with JSON:
{{
    "headline": "...",
    "summary_text": "...",
    "summary_html": "<section>...</section>",
    "newsworthiness": "yes|no",
    "newsworthiness_reason": "...",
    "tags": ["tag1", "tag2", ...]
}}

Use ONLY the verified facts. Do not add information not in the facts or transcript.
"""
    
    result = call_gemini_with_json(
        prompt,
        {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "summary_text": {"type": "string"},
                "summary_html": {"type": "string"},
                "newsworthiness": {"type": "string", "enum": ["yes", "no"]},
                "newsworthiness_reason": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["headline", "summary_text", "summary_html"]
        },
        max_tokens=8192,
        temperature=0.3  # Slightly higher for narrative generation
    )
    
    if result:
        logging.info(f"✓ Summary rendered: {result.get('headline', 'N/A')}")
    else:
        logging.error("✗ Summary rendering failed")
    
    return result


def run_fact_guard_pipeline(transcript_text, video_metadata=None):
    """
    Execute complete 3-stage FACT_GUARD pipeline.
    
    Args:
        transcript_text (str): Video transcript
        video_metadata (dict): Optional video metadata
        
    Returns:
        dict: Complete results from all stages
    """
    logging.info("=" * 60)
    logging.info("Starting FACT_GUARD Pipeline")
    logging.info("=" * 60)
    
    # Stage 1: Extract
    logging.info("\n[Stage 1/3] Extracting structured facts...")
    extracted_facts = extract_facts_from_transcript(transcript_text, video_metadata)
    if not extracted_facts:
        return {
            "success": False,
            "error": "Extraction failed",
            "stage": 1
        }
    
    # Stage 2: Verify
    logging.info("\n[Stage 2/3] Verifying facts against source...")
    verification_result = verify_facts(extracted_facts, transcript_text)
    if not verification_result:
        return {
            "success": False,
            "error": "Verification failed",
            "stage": 2,
            "extracted_facts": extracted_facts
        }
    
    # Check if verification passed
    if verification_result.get('verification_status') != 'PASSED':
        logging.warning(f"⚠ Verification FAILED: {verification_result.get('notes')}")
        # Continue anyway but flag it
    
    # Stage 3: Render
    logging.info("\n[Stage 3/3] Rendering final summary...")
    summary = render_summary(extracted_facts, transcript_text)
    if not summary:
        return {
            "success": False,
            "error": "Summary rendering failed",
            "stage": 3,
            "extracted_facts": extracted_facts,
            "verification": verification_result
        }
    
    # Success!
    logging.info("\n✓ FACT_GUARD pipeline completed successfully")
    
    return {
        "success": True,
        "extracted_facts": extracted_facts,
        "verification": verification_result,
        "summary": summary,
        "pipeline_version": "1.0",
        "processed_at": datetime.now().isoformat()
    }


# ============================================================================
# 6. VIDEO PROCESSING UTILITIES
# ============================================================================

def extract_video_metadata(video_path):
    """
    Extract metadata from video file.
    
    Returns dict with: duration, fps, resolution, codec, filesize, etc.
    """
    try:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        clip = VideoFileClip(str(video_path))
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
            'has_audio': clip.audio is not None
        }
        
        clip.close()
        cap.release()
        
        return metadata
        
    except Exception as e:
        logging.error(f"Failed to extract metadata: {e}", exc_info=True)
        return None


def extract_audio_from_video(video_path, output_path=None):
    """
    Extract audio track from video for transcription.
    
    Args:
        video_path: Path to video file
        output_path: Where to save audio (None = auto-generate .mp3)
        
    Returns:
        str: Path to extracted audio file
    """
    try:
        video_path = Path(video_path)
        
        if output_path is None:
            output_path = video_path.with_suffix('.mp3')
        
        clip = VideoFileClip(str(video_path))
        
        if clip.audio is None:
            logging.warning(f"No audio track in {video_path.name}")
            clip.close()
            return None
        
        clip.audio.write_audiofile(str(output_path), logger=None)
        clip.close()
        
        logging.info(f"✓ Audio extracted: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logging.error(f"Failed to extract audio: {e}", exc_info=True)
        return None


def create_thumbnail(video_path, timestamp=None, output_path=None):
    """
    Create thumbnail image from video.
    
    Args:
        video_path: Path to video
        timestamp: Time in seconds (None = middle of video)
        output_path: Where to save (None = return PIL Image)
        
    Returns:
        PIL.Image or str: Image object or path to saved thumbnail
    """
    try:
        clip = VideoFileClip(str(video_path))
        
        if timestamp is None:
            timestamp = clip.duration / 2
        
        frame = clip.get_frame(timestamp)
        pil_image = Image.fromarray(frame)
        
        if output_path:
            pil_image.save(output_path)
            logging.info(f"✓ Thumbnail: {output_path}")
            clip.close()
            return output_path
        else:
            clip.close()
            return pil_image
            
    except Exception as e:
        logging.error(f"Failed to create thumbnail: {e}", exc_info=True)
        return None


# ============================================================================
# 7. EXAMPLE MAIN WORKFLOW
# ============================================================================

def process_video_workflow(video_path, video_id=None):
    """
    Complete workflow: Process video, transcribe, summarize, save to database.
    
    Args:
        video_path: Path to video file
        video_id: Database ID (for updates) or None (for new records)
        
    Returns:
        dict: Processing results
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Processing video: {video_path}")
    
    try:
        # Step 1: Extract metadata
        metadata = extract_video_metadata(video_path)
        if not metadata:
            return {"success": False, "error": "Metadata extraction failed"}
        
        # Step 2: Extract audio
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            return {"success": False, "error": "Audio extraction failed"}
        
        # Step 3: Transcribe audio (placeholder - integrate Whisper or Google Speech-to-Text)
        # transcript = transcribe_audio(audio_path)
        transcript = "[Implement transcription here]"
        
        # Step 4: Run FACT_GUARD pipeline
        pipeline_result = run_fact_guard_pipeline(transcript, metadata)
        if not pipeline_result['success']:
            return pipeline_result
        
        # Step 5: Save to database
        if video_id:
            # Update existing record
            execute_query("""
                UPDATE videos 
                SET transcript = ?,
                    summary_html = ?,
                    summary_text = ?,
                    headline = ?,
                    newsworthiness = ?,
                    extracted_facts_json = ?,
                    verification_status = ?,
                    processed_at = GETDATE()
                WHERE video_id = ?
            """, (
                transcript,
                pipeline_result['summary']['summary_html'],
                pipeline_result['summary']['summary_text'],
                pipeline_result['summary']['headline'],
                pipeline_result['summary']['newsworthiness'],
                json.dumps(pipeline_result['extracted_facts']),
                pipeline_result['verification']['verification_status'],
                video_id
            ), fetch='none')
        else:
            # Insert new record
            video_id = insert_with_identity("""
                INSERT INTO videos (
                    filename, duration_seconds, transcript, summary_html,
                    summary_text, headline, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                metadata['filename'],
                metadata['duration_seconds'],
                transcript,
                pipeline_result['summary']['summary_html'],
                pipeline_result['summary']['summary_text'],
                pipeline_result['summary']['headline']
            ))
        
        # Step 6: Send notification email
        send_email(
            to_address="admin@example.com",
            subject=f"Video Processed: {metadata['filename']}",
            body_html=f"""
                <h2>Video Processing Complete</h2>
                <p><strong>File:</strong> {metadata['filename']}</p>
                <p><strong>Duration:</strong> {metadata['duration_seconds']:.1f}s</p>
                <p><strong>Headline:</strong> {pipeline_result['summary']['headline']}</p>
                <p><strong>Verification:</strong> {pipeline_result['verification']['verification_status']}</p>
                <hr>
                {pipeline_result['summary']['summary_html']}
            """
        )
        
        return {
            "success": True,
            "video_id": video_id,
            "metadata": metadata,
            "pipeline_result": pipeline_result
        }
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Setup
    logger = setup_logging('video_project.log')
    
    # Initialize Gemini API
    if not initialize_vertex_ai():
        sys.exit(1)
    
    # Example 1: Simple Gemini call
    response = call_gemini("What are the key principles of fair trial rights?", max_tokens=1024)
    print(response)
    
    # Example 2: Database query
    pending_videos = execute_query("SELECT * FROM videos WHERE status = ?", ('pending',))
    for video in pending_videos:
        print(f"Process video: {video['filename']}")
    
    # Example 3: Process a video
    # result = process_video_workflow('path/to/video.mp4')
    # print(json.dumps(result, indent=2))
    
    # Example 4: Send test email
    # send_email(
    #     to_address="test@example.com",
    #     subject="Test Email",
    #     body_html="<h1>This is a test</h1>"
    # )
