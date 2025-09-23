@echo off
REM DocketWatch Simple RSS Processor Batch File
REM 
REM This batch file runs the simplified end-to-end RSS processing workflow:
REM 1. RSS monitoring for new PACER case events with PDF download
REM 2. Retry failed PDF downloads for recent events
REM 3. Basic reporting
REM
REM This version avoids database schema compatibility issues
REM Schedule this to run every 15-30 minutes for optimal coverage
REM

echo Starting DocketWatch Simple RSS Processor at %date% %time%

cd /d u:\docketwatch\python

python docketwatch_simple_rss_processor.py

echo DocketWatch Simple RSS Processor finished at %date% %time%

REM Add a small delay to see results in case of manual execution
timeout /t 3 /nobreak >nul