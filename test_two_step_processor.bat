@echo off
REM Two-step PACER processing: Metadata extraction + PDF download
REM Case Event ID: 664EBE70-7066-4A39-A265-9A50A6E21694

echo ===========================================
echo DocketWatch PACER Two-Step Processor Test
echo ===========================================
echo Case Event ID: 664EBE70-7066-4A39-A265-9A50A6E21694
echo Start Time: %date% %time%
echo ===========================================

cd /d "u:\docketwatch\python"

echo.
echo STEP 1: Running combined processor (metadata + download attempt)...
echo.
"C:\Program Files\Python312\python.exe" combined_pacer_pdf_processor.py 664EBE70-7066-4A39-A265-9A50A6E21694

echo.
echo Step 1 completed with exit code: %ERRORLEVEL%
echo.

echo STEP 2: Running dedicated PDF downloader as backup...
echo.
"C:\Program Files\Python312\python.exe" extract_pacer_pdf_file.py 664EBE70-7066-4A39-A265-9A50A6E21694

echo.
echo ===========================================
echo Both steps completed at: %date% %time%
echo Final exit code: %ERRORLEVEL%
echo ===========================================

REM Keep the window open if run manually
if "%1"=="" pause