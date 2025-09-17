@echo off
REM Test execution of combined_pacer_pdf_processor.py
REM Case Event ID: 664EBE70-7066-4A39-A265-9A50A6E21694

echo ===========================================
echo DocketWatch PACER PDF Processor Test
echo ===========================================
echo Case Event ID: 664EBE70-7066-4A39-A265-9A50A6E21694
echo Start Time: %date% %time%
echo ===========================================

cd /d "u:\docketwatch\python"

"C:\Program Files\Python312\python.exe" combined_pacer_pdf_processor.py 664EBE70-7066-4A39-A265-9A50A6E21694

echo ===========================================
echo Execution completed at: %date% %time%
echo Exit code: %ERRORLEVEL%
echo ===========================================

REM Keep the window open if run manually
if "%1"=="" pause