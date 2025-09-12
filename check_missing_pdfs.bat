@echo off
REM Check for Missing PDF Files and Update Status
REM This script finds documents marked as downloaded but with missing PDF files

echo.
echo ========================================
echo    MISSING PDF STATUS UPDATER
echo ========================================
echo.
echo This script will:
echo - Check documents marked as downloaded
echo - Verify if PDF files actually exist
echo - Update status to 'Missing' if files not found
echo.

cd /d "u:\docketwatch\python"

echo Running PDF existence check...
echo.

python update_missing_pdf_status.py

echo.
echo ========================================
echo Process completed!
echo ========================================
echo.
pause
