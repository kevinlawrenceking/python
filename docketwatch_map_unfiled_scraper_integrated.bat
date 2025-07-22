@echo off
REM DocketWatch Integrated Unfiled Scraper with PDF Download
REM This batch file runs the integrated unfiled scraper that downloads PDFs inline
REM ensuring users only see records when PDFs are available.

REM Set working directory
cd /d "U:\docketwatch\python"

REM Get current date in YYYY-MM-DD format
for /f "tokens=1-3 delims=/" %%a in ("%date%") do (
    set month=%%a
    set day=%%b
    set year=%%c
)

REM Handle leading zeros and format properly
set month=0%month%
set month=%month:~-2%
set day=0%day%
set day=%day:~-2%

set current_date=%year%-%month%-%day%

echo ============================================
echo DocketWatch Integrated Unfiled Scraper
echo Date: %current_date%
echo ============================================
echo.

REM Run the integrated scraper
echo Starting integrated unfiled record scraping with PDF download...
python docketwatch_map_unfiled_scraper.py %current_date%

if %errorlevel% equ 0 (
    echo.
    echo   Integrated scraper completed successfully
    echo   - New unfiled records have been processed
    echo   - PDFs have been downloaded and saved
    echo   - Document records have been created
    echo   - Records are ready for user access
) else (
    echo.
    echo   Integrated scraper failed with error code %errorlevel%
    echo   - Check logs for details
    echo   - Some records may not have been processed
)

echo.
echo Process completed at %time%
echo ============================================

REM Optional: Pause to see results (comment out for automated runs)
pause
