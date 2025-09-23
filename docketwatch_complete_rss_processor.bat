@echo off
REM DocketWatch Complete RSS Processor Batch File
REM 
REM This batch file runs the complete end-to-end RSS processing workflow:
REM 1. RSS monitoring for new PACER case events
REM 2. PDF download (including iframe-based PDFs)
REM 3. AI document summarization
REM 4. Enhanced email notifications
REM 5. Retry failed downloads
REM
REM Schedule this to run every 15-30 minutes for optimal coverage
REM

echo Starting DocketWatch Complete RSS Processor at %date% %time%

cd /d u:\docketwatch\python

python docketwatch_complete_rss_processor.py

echo DocketWatch Complete RSS Processor finished at %date% %time%

REM Add a small delay to see results in case of manual execution
timeout /t 5 /nobreak >nul