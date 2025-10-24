## DocketWatch Pipeline Overview

The run_docketwatch_pipeline.py script orchestrates a comprehensive workflow for processing court case documents from the PACER (Public Access to Court Electronic Records) system. The pipeline consists of five sequential stages, each handling a specific aspect of document processing:

### Pipeline Stages:

1. **Metadata Extraction** (Stage 1)
   - Script: extract_pacer_pdf_metadata.py
   - Purpose: Extracts metadata about PDF documents from PACER court filing pages
   - Process:
     - Logs into PACER using stored credentials
     - Navigates to the specific case event page
     - Extracts document links, titles, and other metadata
     - Stores this information in the `documents` table with status "pending"

2. **Document Download** (Stage 2)
   - Script: process_pacer_event_pdf.py
   - Purpose: Downloads the actual PDF files from PACER based on the metadata
   - Process:
     - Logs into PACER
     - Downloads each PDF document for the case event
     - Stores files on a network share at `\\10.146.176.84\general\docketwatch\docs\cases`
     - Updates database with file paths

3. **OCR Processing** (Stage 3)
   - Function: `perform_ocr_for_documents` (from scraper_base.py)
   - Purpose: Extracts text content from PDF documents
   - Process:
     - First attempts to extract embedded text directly from PDFs
     - If insufficient text found, runs OCR (Optical Character Recognition)
     - Uses PyPDF2 for text extraction and pytesseract for image-based OCR
     - Stores extracted text in the database

4. **Document-Level AI Summarization** (Stage 4)
   - Function: `generate_ai_summary_for_documents` (from scraper_base.py)
   - Purpose: Creates summaries for individual documents
   - Process:
     - Uses Google's Gemini AI (`gemini-2.5-pro`)
     - Provides case context, event description, and document text to the AI
     - Generates a concise legal summary for each document
     - Stores both plain text and HTML-formatted summaries in the database

5. **Event-Level Summarization** (Stage 5)
   - Script: summarize_case_event_ai.py
   - Purpose: Creates an overall summary of the case event based on all documents
   - Process:
     - Collects summaries of all documents related to the event
     - Uses Gemini AI to create a comprehensive event summary
     - Stores the event-level summary in the database

### Additional Processes:

- **Case-Level Summarization**
  - Script: pacer_case_summarizer.py
  - Purpose: Creates an overall summary of the entire case
  - Process:
    - Logs into PACER and retrieves the full case docket
    - Gets information about parties, counsel, and all events
    - Generates a comprehensive case summary using Gemini AI
    - Updates the `cases.summarize` and `cases.summarize_html` fields

### Database Structure:

The pipeline works with several key tables:
- `cases`: Stores case-level information
- `case_events`: Tracks individual events within a case (filings, hearings, etc.)
- `documents`: Stores document metadata and content for each event
- `utilities`: Contains configuration like API keys

### Workflow Management:

- The pipeline processes up to 10 case events at a time (configurable)
- Each case event progresses through the 5 stages sequentially
- The `stage_completed` field tracks progress (0-5)
- Extensive logging captures success/failure at each step
- Task runs are recorded in the database for monitoring

### Error Handling:

- Each stage is wrapped in try/except blocks
- Errors are logged but don't halt the entire pipeline
- Database commits are made after each successful stage

## Technical Implementation

The pipeline uses:
- **Selenium** for web automation (PACER login and navigation)
- **PyPDF2** for PDF text extraction
- **pytesseract** and **OpenCV** for OCR
- **Google Gemini AI** for document and case summarization
- **SQL Server** (via pyodbc) for data storage
- **Network file storage** for document archiving

This robust pipeline automates the end-to-end process of collecting, processing, and summarizing legal documents from the PACER system, making legal information more accessible and understandable.