import os
import re
import sys
import json
import cv2
import numpy as np
import pyodbc
import PyPDF2
import pytesseract
import markdown2
from bs4 import BeautifulSoup
from datetime import datetime
from pdf2image import convert_from_path
from cleantext import clean as clean_unicode
import unicodedata
import google.generativeai as genai

# Test the scraper_base import separately
try:
    from scraper_base import log_message
    print("Test: Successfully imported log_message from scraper_base.")
except ImportError as e:
    print(f"Test: WARNING: Could not import log_message from scraper_base: {e}", file=sys.stderr)
    # Define a dummy log_message for this test if needed
    def log_message(*args, **kwargs):
        print(f"Test: Fallback log_message: {args}", file=sys.stderr)
except Exception as e:
    print(f"Test: CRITICAL ERROR during log_message import: {e}", file=sys.stderr)
    def log_message(*args, **kwargs):
        print(f"Test: Fallback log_message (critical error): {args}", file=sys.stderr)

print("Test: All core libraries imported successfully!")
log_message(None, None, "INFO", "Test: This message should appear if log_message works.")

# Try a simple CV2 operation to check its health
try:
    dummy_img = np.zeros((10,10,3), dtype=np.uint8)
    cv2.cvtColor(dummy_img, cv2.COLOR_BGR2GRAY)
    print("Test: OpenCV seems to be working.")
except Exception as e:
    print(f"Test: ERROR: OpenCV test failed: {e}", file=sys.stderr)

# Try a simple PyTesseract check
try:
    dummy_img_path = "dummy_image_for_tesseract_test.png"
    cv2.imwrite(dummy_img_path, dummy_img) # Create a dummy image
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe" # Ensure path is correct for test
    text = pytesseract.image_to_string(dummy_img_path)
    print("Test: PyTesseract seems to be working (even if no text found).")
    os.remove(dummy_img_path) # Clean up
except Exception as e:
    print(f"Test: ERROR: PyTesseract test failed: {e}", file=sys.stderr)

print("Test: Script finished.")