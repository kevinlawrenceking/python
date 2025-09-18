@echo off
echo =============================== >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
echo START: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log

set CASE_EVENT_ID=%1

if "%CASE_EVENT_ID%"=="" (
    echo ERROR: Case Event ID is required >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
    exit /b 1
)

echo Processing Case Event ID: %CASE_EVENT_ID% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log

REM Step 1: Extract PDF metadata
echo STEP 1 START: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
"C:\Program Files\Python312\python.exe" \\10.146.176.84\general\DOCKETWATCH\python\extract_pacer_pdf_metadata.py %CASE_EVENT_ID% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log 2>&1
if %errorlevel% neq 0 (
    echo STEP 1 FAILED: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
    exit /b %errorlevel%
)
echo STEP 1 SUCCESS: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log

REM Wait 5 seconds before starting step 2 to avoid Chrome conflicts
echo Waiting 5 seconds before Step 2... >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
timeout /t 5 /nobreak >nul

REM Step 2: Process PDF final  
echo STEP 2 START: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
"C:\Program Files\Python312\python.exe" \\10.146.176.84\general\DOCKETWATCH\python\process_pacer_event_pdf_final.py %CASE_EVENT_ID% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log 2>&1
if %errorlevel% neq 0 (
    echo STEP 2 FAILED: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
    exit /b %errorlevel%
)
echo STEP 2 SUCCESS: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log

echo END: %date% %time% >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log
echo. >>\\10.146.176.84\general\DOCKETWATCH\python\logs\single_case_event.log

exit /b 0