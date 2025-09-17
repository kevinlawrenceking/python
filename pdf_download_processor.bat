@echo off
echo =============================== >>u:\DOCKETWATCH\python\pdf_processor_log.txt
echo START: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt

set CASE_EVENT_ID=%1

if "%CASE_EVENT_ID%"=="" (
    echo ERROR: Case Event ID is required >>u:\DOCKETWATCH\python\pdf_processor_log.txt
    exit /b 1
)

echo Processing Case Event ID: %CASE_EVENT_ID% >>u:\DOCKETWATCH\python\pdf_processor_log.txt

REM Step 1: Extract metadata
echo STEP 1 START: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt
"C:\Program Files\Python312\python.exe" u:\DOCKETWATCH\python\extract_pacer_pdf_metadata.py %CASE_EVENT_ID% >>u:\DOCKETWATCH\python\pdf_processor_log.txt 2>&1
if %errorlevel% neq 0 (
    echo STEP 1 FAILED: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt
    exit /b %errorlevel%
)
echo STEP 1 SUCCESS: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt

REM Wait 5 seconds before starting step 2 to avoid Chrome conflicts
echo Waiting 5 seconds before Step 2... >>u:\DOCKETWATCH\python\pdf_processor_log.txt
timeout /t 5 /nobreak >nul

REM Step 2: Process PDF final  
echo STEP 2 START: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt
"C:\Program Files\Python312\python.exe" u:\DOCKETWATCH\python\process_pacer_event_pdf_final.py %CASE_EVENT_ID% >>u:\DOCKETWATCH\python\pdf_processor_log.txt 2>&1
if %errorlevel% neq 0 (
    echo STEP 2 FAILED: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt
    exit /b %errorlevel%
)
echo STEP 2 SUCCESS: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt

echo END: %date% %time% >>u:\DOCKETWATCH\python\pdf_processor_log.txt
echo. >>u:\DOCKETWATCH\python\pdf_processor_log.txt

exit /b 0