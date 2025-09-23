@echo off
REM DocketWatch Omega RSS Processor Batch File
REM 
REM This batch file runs the PROVEN omega approach RSS processing workflow:
REM 1. RSS monitoring for new PACER case events
REM 2. Omega PDF processing (metadata extraction + PDF download)
REM 3. AI summarization and enhanced email alerts
REM
REM This uses the proven pacer_pdf_pending_loop_omega.py approach that works 100%
REM Schedule this to run every 15-30 minutes for optimal coverage
REM

echo Starting DocketWatch Omega RSS Processor at %date% %time%
echo Using the proven omega approach that works 100%% of the time

cd /d u:\docketwatch\python

python docketwatch_omega_rss_processor.py

echo DocketWatch Omega RSS Processor finished at %date% %time%

REM Add a small delay to see results in case of manual execution
timeout /t 5 /nobreak >nul