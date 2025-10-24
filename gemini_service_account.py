"""
Gemini API Service Account Helper - Single Source of Truth
==========================================================
All Gemini API calls in the project should use this module.
Uses Vertex AI with service account authentication (NO API KEYS).

Usage:
    from gemini_service_account import call_gemini, call_gemini_json, get_available_model
    
    # Simple text call
    response = call_gemini("Summarize this text...", max_tokens=8192)
    
    # JSON response with schema
    result = call_gemini_json("Extract facts...", schema, max_tokens=8192)
    
    # Get best available model
    model_name = get_available_model()
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

import vertexai
from vertexai.generative_models import (
    GenerativeModel, 
    GenerationConfig, 
    SafetySetting, 
    HarmCategory, 
    HarmBlockThreshold,
    Content,
    Part
)

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ID = "tmz-docketwatch-prod"  # Correct GCP project ID from service account
REGION = "us-central1"
DEFAULT_MODEL = "gemini-2.5-flash"  # Stable production model (max 8192 tokens)

# Service account file (absolute path)
SCRIPT_DIR = Path(__file__).parent.absolute()
SERVICE_ACCOUNT_FILE = SCRIPT_DIR / "docketwatch-service-account.json"

# Safety settings for legal documents (allow sensitive content)
SAFETY_SETTINGS = [
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
    ),
]

# Model priority list (try in order)
MODEL_PRIORITY = [
    "gemini-2.5-flash",      # Primary: Gemini 2.5 Flash (8192 max output tokens)
    "gemini-1.5-flash-002",  # Fallback 1
    "gemini-1.5-flash",      # Fallback 2
    "gemini-1.5-pro-002",    # Fallback 3 (slower but more capable)
    "gemini-1.5-pro",        # Fallback 4
]

# Initialize Vertex AI once at module load
_INITIALIZED = False

def _initialize_vertex_ai():
    """Initialize Vertex AI with service account. Called automatically on first use."""
    global _INITIALIZED
    
    if _INITIALIZED:
        return
    
    try:
        if not SERVICE_ACCOUNT_FILE.exists():
            raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        
        # Set environment variable for authentication
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(SERVICE_ACCOUNT_FILE)
        
        # Initialize Vertex AI
        vertexai.init(project=PROJECT_ID, location=REGION)
        
        logging.info(f"✓ Vertex AI initialized: Project={PROJECT_ID}, Location={REGION}")
        _INITIALIZED = True
        
    except Exception as e:
        logging.error(f"✗ Failed to initialize Vertex AI: {e}", exc_info=True)
        raise


# ============================================================================
# MODEL SELECTION
# ============================================================================

def get_available_model(preferred_model: Optional[str] = None) -> str:
    """
    Get the best available Gemini model.
    
    Args:
        preferred_model: Optional specific model name to use
        
    Returns:
        str: Model name to use
    """
    _initialize_vertex_ai()
    
    if preferred_model:
        return preferred_model
    
    # For now, just return default model
    # In the future, could check model availability via API
    return DEFAULT_MODEL


# ============================================================================
# CORE API FUNCTIONS
# ============================================================================

def call_gemini(
    prompt: str,
    max_tokens: int = 8192,
    temperature: float = 0.2,
    model_name: Optional[str] = None,
    safety_settings: Optional[List[SafetySetting]] = None
) -> Optional[str]:
    """
    Call Gemini API with text prompt.
    
    Args:
        prompt: Text prompt/question
        max_tokens: Maximum output tokens (default 8192, max 8192 for gemini-2.5-flash)
        temperature: Creativity level 0.0-1.0 (0.2 for factual)
        model_name: Specific model to use (None = use default)
        safety_settings: Custom safety settings (None = use defaults)
        
    Returns:
        str: Model response text or None on error
        
    Example:
        response = call_gemini("Summarize this document...", max_tokens=8192)
    """
    _initialize_vertex_ai()
    
    try:
        # Get model
        model = GenerativeModel(get_available_model(model_name))
        
        # Enforce maximum token limit for gemini-2.5-flash
        if max_tokens > 8192:
            logging.warning(f"max_tokens={max_tokens} exceeds model limit, capping at 8192")
            max_tokens = 8192
        
        # Generation config
        config = GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
            top_k=40
        )
        
        # Use provided safety settings or defaults
        settings = safety_settings if safety_settings else SAFETY_SETTINGS
        
        # Generate response
        response = model.generate_content(
            prompt,
            generation_config=config,
            safety_settings=settings,
            stream=False
        )
        
        # Handle response
        if not response or not response.candidates:
            logging.error("No response from Gemini API")
            return None
        
        candidate = response.candidates[0]
        
        # Check finish reason
        finish_reason = candidate.finish_reason
        finish_reason_value = finish_reason.value if hasattr(finish_reason, 'value') else finish_reason
        
        if finish_reason_value == 1:  # STOP - normal completion
            return candidate.content.parts[0].text
            
        elif finish_reason_value == 2:  # MAX_TOKENS - truncated
            logging.warning("Response truncated due to token limit")
            if candidate.content and candidate.content.parts:
                text = candidate.content.parts[0].text
                logging.warning(f"Returning partial response ({len(text)} chars)")
                return text
            return None
            
        elif finish_reason_value == 3:  # SAFETY - blocked by filters
            logging.error("Response blocked by safety filters")
            return None
            
        elif finish_reason_value == 4:  # RECITATION - copyright issue
            logging.error("Response blocked due to recitation/copyright")
            return None
            
        else:
            logging.error(f"Unknown finish reason: {finish_reason_value}")
            return None
            
    except Exception as e:
        logging.error(f"Gemini API call failed: {e}", exc_info=True)
        return None


def call_gemini_json(
    prompt: str,
    json_schema: Dict[str, Any],
    max_tokens: int = 8192,
    temperature: float = 0.2,
    model_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Call Gemini API and enforce JSON response with schema.
    Includes auto-repair for truncated JSON.
    
    Args:
        prompt: Extraction prompt
        json_schema: JSON schema with type/properties/required
        max_tokens: Output token limit (8192 max for gemini-2.5-flash)
        temperature: Creativity (0.2 for structured extraction)
        model_name: Specific model to use (None = use default)
        
    Returns:
        dict: Parsed JSON response or None
        
    Example:
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["summary"]
        }
        result = call_gemini_json("Extract key info...", schema)
    """
    _initialize_vertex_ai()
    
    try:
        # Add JSON schema to prompt
        full_prompt = f"""{prompt}

CRITICAL: Respond with ONLY valid JSON matching this schema:
{json.dumps(json_schema, indent=2)}

Rules:
- Start with {{ and end with }}
- Use double quotes for strings
- Escape special characters in strings
- No markdown code blocks, no explanations, ONLY JSON
- Ensure all required fields are present
"""
        
        # Call API
        response_text = call_gemini(
            full_prompt, 
            max_tokens=max_tokens, 
            temperature=temperature,
            model_name=model_name
        )
        
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
            repaired = _auto_close_json(response_text)
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


def _auto_close_json(text: str) -> str:
    """
    Attempt to repair truncated JSON by closing open structures.
    
    Args:
        text: Potentially truncated JSON string
        
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
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================================

def generate_content_vertex(
    prompt: str, 
    temperature: float = 0.5, 
    max_tokens: int = 2048
) -> str:
    """
    Legacy compatibility function for old code.
    
    DEPRECATED: Use call_gemini() instead.
    """
    logging.warning("generate_content_vertex() is deprecated. Use call_gemini() instead.")
    result = call_gemini(prompt, max_tokens=max_tokens, temperature=temperature)
    return result if result else ""


# ============================================================================
# BATCH PROCESSING HELPERS
# ============================================================================

def call_gemini_with_retry(
    prompt: str,
    max_retries: int = 3,
    **kwargs
) -> Optional[str]:
    """
    Call Gemini with automatic retries on failure.
    
    Args:
        prompt: Text prompt
        max_retries: Number of retry attempts
        **kwargs: Additional arguments passed to call_gemini()
        
    Returns:
        str: Response or None after all retries exhausted
    """
    import time
    
    for attempt in range(max_retries):
        try:
            response = call_gemini(prompt, **kwargs)
            if response:
                return response
            
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed, retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries} error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    
    return None


# ============================================================================
# TESTING
# ============================================================================

def test_connection():
    """Test the Vertex AI service account connection."""
    print("Testing Gemini API via Service Account...")
    print(f"Service Account File: {SERVICE_ACCOUNT_FILE}")
    print(f"File Exists: {SERVICE_ACCOUNT_FILE.exists()}")
    
    try:
        _initialize_vertex_ai()
        print("✓ Initialization successful")
        
        # Test simple call
        result = call_gemini("Say 'OK' if you can hear me.", temperature=0, max_tokens=100)
        
        if result:
            print(f"✓ API Call successful: {result}")
            return True
        else:
            print("✗ API Call failed: No response")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run test when module is executed directly
    import sys
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    success = test_connection()
    sys.exit(0 if success else 1)
