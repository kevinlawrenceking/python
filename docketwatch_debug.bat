@echo off
REM Debug mode batch file for docketwatch_case_events_alert_plus2.py
REM This sets debug mode and runs the script with a case ID
REM Usage: docketwatch_debug.bat [case_id]

if "%1"=="" (
    echo Usage: %0 [case_id]
    echo Example: %0 107756
    echo.
    echo This will run the case alert script in DEBUG MODE
    echo Emails will only be sent to Kevin.King@tmz.com
    exit /b 1
)

echo Setting DEBUG MODE (emails to Kevin only)...
set DOCKETWATCH_DEBUG=Y

echo Running case alert script for case ID: %1
python docketwatch_case_events_alert_plus2.py %1

echo Done.
pause