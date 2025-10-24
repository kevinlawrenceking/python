"""
PDF Operations Module for DocketWatch
====================================

This module handles all PDF-related operations including:
- Downloading PDFs from various court systems
- OCR processing for text extraction
- PDF validation and integrity checking
- Metadata extraction

Extracted from scraper_base.py to create a focused, reusable component.
"""

import os
import zipfile
import time
import logging
import re
import unicodedata
from datetime import datetime

# OCR and PDF processing
import PyPDF2
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError

# === PDF Validation ===

def is_valid_pdf(file_path):
    """
    Check if a file is a valid PDF by examining its header.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        bool: True if valid PDF, False otherwise
    """
    try:
        with open(file_path, 'rb') as f:
            return f.read(5) == b'%PDF-'
    except Exception:
        return False

def get_pdf_metadata(file_path):
    """
    Extract metadata from a PDF file.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        dict: PDF metadata including page count, creation date, etc.
    """
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            metadata = {
                'page_count': len(reader.pages),
                'file_size': os.path.getsize(file_path),
                'is_encrypted': reader.is_encrypted,
                'metadata': reader.metadata if hasattr(reader, 'metadata') else {}
            }
            return metadata
    except Exception as e:
        logging.error(f"Failed to extract PDF metadata from {file_path}: {e}")
        return {'error': str(e)}

# === Image Preprocessing for OCR ===

def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Preprocess an image for better OCR results.
    
    Args:
        image: OpenCV image array (BGR format)
        
    Returns:
        np.ndarray: Preprocessed binary image
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to reduce noise while preserving edges
    gray = cv2.bilateralFilter(gray, d=5, sigmaColor=75, sigmaSpace=75)
    
    # Apply binary threshold using Otsu's method
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Deskewing (straighten rotated text)
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) > 0.5:  # Only rotate if significant skew detected
            (h, w) = thresh.shape[:2]
            M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
            thresh = cv2.warpAffine(thresh, M, (w, h), 
                                  flags=cv2.INTER_CUBIC, 
                                  borderMode=cv2.BORDER_REPLICATE)
    
    return thresh

# === Text Cleaning ===

def clean_ocr_text(text: str) -> str:
    """
    Clean and normalize OCR-extracted text.
    
    Args:
        text: Raw OCR text
        
    Returns:
        str: Cleaned and normalized text
    """
    if not text:
        return ""
    
    # Remove common OCR artifacts and headers
    text = re.sub(r'^[A-Z ]+ v\.? [A-Z ]+\n', '', text, flags=re.MULTILINE)  # Case headers
    text = re.sub(r'^Page \d+\s*\n', '', text, flags=re.MULTILINE)  # Page numbers
    text = re.sub(r'^\d+\s*\n', '', text, flags=re.MULTILINE)  # Standalone numbers
    
    # Fix hyphenated words split across lines
    text = re.sub(r'-\n(?=\w)', '', text)
    
    # Convert single newlines to spaces (paragraph preservation)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    
    # Fix common OCR character replacements
    text = text.replace('"', '"').replace('"', '"').replace('–', '-')
    
    # Normalize Unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    return text.strip()

# === OCR Processing ===

def extract_text_from_pdf(file_path, use_ocr=True):
    """
    Extract text from a PDF using embedded text layer and/or OCR.
    
    Args:
        file_path (str): Path to the PDF file
        use_ocr (bool): Whether to fall back to OCR if text layer is insufficient
        
    Returns:
        str: Extracted and cleaned text
    """
    if not is_valid_pdf(file_path):
        raise ValueError(f"Invalid PDF file: {file_path}")
    
    text = ""
    
    # First, try to extract embedded text layer
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        logging.warning(f"Failed to extract embedded text from {file_path}: {e}")
        text = ""
    
    # If embedded text is insufficient, use OCR
    if use_ocr and len(text.strip()) < 200:
        logging.info(f"Embedded text insufficient ({len(text)} chars), running OCR on {file_path}")
        try:
            # Convert PDF pages to images
            images = convert_from_path(file_path, dpi=300, poppler_path=r"C:\\Poppler\\bin")
            
            ocr_text = ""
            for i, pil_image in enumerate(images):
                # Convert PIL image to OpenCV format
                img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                
                # Preprocess for better OCR
                processed_img = preprocess_image(img)
                
                # Run OCR
                page_text = pytesseract.image_to_string(
                    processed_img, 
                    config="--oem 1 --psm 6"  # Use LSTM OCR engine, uniform text block
                )
                ocr_text += page_text + "\n"
                
                # Log progress for large documents
                if len(images) > 5 and (i + 1) % 5 == 0:
                    logging.info(f"OCR progress: {i+1}/{len(images)} pages completed")
            
            text = ocr_text
            
        except PDFPageCountError as e:
            raise ValueError(f"Unreadable PDF (corrupt or password protected): {file_path} — {e}")
        except Exception as e:
            raise RuntimeError(f"OCR processing failed for {file_path}: {e}")
    
    # Clean and return the text
    return clean_ocr_text(text)

# === Document Processing for Database ===

def perform_ocr_for_documents(cursor, case_event_id, docs_root_dir):
    """
    Process all documents for a case_event that need OCR.
    Updates the database with extracted text.
    
    Args:
        cursor: Database cursor
        case_event_id: ID of the case event
        docs_root_dir: Root directory for document storage
        
    Returns:
        int: Number of documents successfully processed
    """
    # Get documents that need OCR
    cursor.execute("""
        SELECT doc_uid, rel_path
        FROM docketwatch.dbo.documents
        WHERE fk_case_event = ? 
          AND (ocr_text IS NULL OR LEN(ocr_text) < 10)
          AND rel_path IS NOT NULL 
          AND rel_path NOT IN ('pending', '')
    """, (case_event_id,))
    
    rows = cursor.fetchall()
    if not rows:
        logging.info(f"No documents need OCR for case_event {case_event_id}")
        return 0

    processed_count = 0
    
    for doc_uid, rel_path in rows:
        abs_path = os.path.join(docs_root_dir, rel_path)
        
        if not os.path.isfile(abs_path):
            logging.error(f"File not found: {abs_path}")
            continue

        try:
            # Extract text using OCR
            extracted_text = extract_text_from_pdf(abs_path)
            
            if len(extracted_text.strip()) < 100:
                logging.warning(f"OCR text too short ({len(extracted_text)} chars) for {rel_path}")
                continue

            # Update database
            cursor.execute("""
                UPDATE docketwatch.dbo.documents
                SET ocr_text = ?, ai_processed_at = ?
                WHERE doc_uid = ?
            """, (extracted_text, datetime.now(), doc_uid))
            
            cursor.connection.commit()
            processed_count += 1
            
            logging.info(f"OCR completed for {rel_path} ({len(extracted_text)} chars)")
            
        except Exception as e:
            logging.error(f"OCR failed for {rel_path}: {e}")
            continue

    logging.info(f"OCR processing complete: {processed_count}/{len(rows)} documents processed")
    return processed_count

# === PDF Download Operations ===

def download_pdf_from_url(url, destination_path, timeout=30):
    """
    Download a PDF from a URL to a local path.
    
    Args:
        url (str): URL to download from
        destination_path (str): Local file path to save to
        timeout (int): Request timeout in seconds
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import requests
        
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verify the downloaded file is a valid PDF
        if not is_valid_pdf(destination_path):
            os.remove(destination_path)
            raise ValueError("Downloaded file is not a valid PDF")
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to download PDF from {url}: {e}")
        if os.path.exists(destination_path):
            os.remove(destination_path)
        return False

def extract_zip_and_organize_pdfs(zip_path, destination_dir, naming_pattern="E{doc_id}.pdf"):
    """
    Extract PDFs from a ZIP file and organize them with proper naming.
    
    Args:
        zip_path (str): Path to the ZIP file
        destination_dir (str): Directory to extract to
        naming_pattern (str): Pattern for renaming files (can include {doc_id})
        
    Returns:
        list: List of extracted PDF file paths
    """
    extracted_files = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_name in zip_ref.namelist():
                if file_name.lower().endswith('.pdf'):
                    # Extract to temporary location
                    temp_path = os.path.join(destination_dir, file_name)
                    zip_ref.extract(file_name, destination_dir)
                    
                    # Validate PDF
                    if is_valid_pdf(temp_path):
                        # Get file size for validation
                        file_size = os.path.getsize(temp_path)
                        
                        if file_size >= 2048:  # At least 2KB
                            extracted_files.append(temp_path)
                            logging.info(f"Extracted valid PDF: {file_name} ({file_size} bytes)")
                        else:
                            logging.warning(f"PDF too small, removing: {file_name} ({file_size} bytes)")
                            os.remove(temp_path)
                    else:
                        logging.warning(f"Invalid PDF, removing: {file_name}")
                        os.remove(temp_path)
        
        return extracted_files
        
    except Exception as e:
        logging.error(f"Failed to extract ZIP file {zip_path}: {e}")
        return []

# === Batch Processing ===

def batch_process_pending_pdfs(cursor, limit=100):
    """
    Process a batch of documents that need PDF download/processing.
    
    Args:
        cursor: Database cursor
        limit (int): Maximum number of documents to process
        
    Returns:
        dict: Processing results summary
    """
    # This would implement the batch processing logic
    # for multiple case events that need PDF processing
    pass

# === Utility Functions ===

def cleanup_temp_files(directory, max_age_hours=24):
    """
    Clean up temporary files older than specified age.
    
    Args:
        directory (str): Directory to clean
        max_age_hours (int): Maximum age in hours before deletion
    """
    try:
        import time
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for filename in os.listdir(directory):
            if filename.endswith('.tmp') or filename.endswith('.crdownload'):
                file_path = os.path.join(directory, filename)
                if os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    logging.info(f"Cleaned up temp file: {filename}")
                    
    except Exception as e:
        logging.error(f"Failed to cleanup temp files in {directory}: {e}")

def get_pdf_processing_stats(cursor, case_event_id=None):
    """
    Get statistics about PDF processing status.
    
    Args:
        cursor: Database cursor
        case_event_id: Optional case event ID to filter by
        
    Returns:
        dict: Processing statistics
    """
    where_clause = "WHERE fk_case_event = ?" if case_event_id else ""
    params = [case_event_id] if case_event_id else []
    
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total_docs,
            SUM(CASE WHEN rel_path = 'pending' THEN 1 ELSE 0 END) as pending_download,
            SUM(CASE WHEN ocr_text IS NULL OR LEN(ocr_text) < 10 THEN 1 ELSE 0 END) as needs_ocr,
            SUM(CASE WHEN summary_ai IS NULL THEN 1 ELSE 0 END) as needs_summary
        FROM docketwatch.dbo.documents
        {where_clause}
    """, params)
    
    row = cursor.fetchone()
    return {
        'total_documents': row.total_docs,
        'pending_download': row.pending_download,
        'needs_ocr': row.needs_ocr,
        'needs_summary': row.needs_summary
    }
