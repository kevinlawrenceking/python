@echo off
REM Simple PACER PDF Download Test Batch File
REM Usage: simple_pacer_pdf_test.bat [case_event_id]

echo.
echo ========================================
echo    SIMPLE PACER PDF DOWNLOAD TEST
echo ========================================
echo.

if "%1"=="" (
    echo Usage: simple_pacer_pdf_test.bat [case_event_id]
    echo.
    echo Example:
    echo simple_pacer_pdf_test.bat CC8013B7-EF21-428A-95A7-5053492BF184
    echo.
    pause
    exit /b 1
)

set CASE_EVENT_ID=%1

echo Case Event ID: %CASE_EVENT_ID%
echo.
echo Running lightweight enhanced downloader...
echo.

cd /d "u:\docketwatch\python"

python lightweight_enhanced_downloader.py %CASE_EVENT_ID%

echo.
echo ========================================
echo Download process completed!
echo ========================================
echo.
pause
