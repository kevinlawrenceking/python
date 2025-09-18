@echo off
echo ========================================
echo Manual RSS Trigger Test
echo Time: %date% %time%
echo ========================================

cd /d "u:\docketwatch\python"

REM Create a timestamp for this manual run
set timestamp=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set timestamp=%timestamp: =0%

echo Manual execution started at: %timestamp%
echo.

REM Run the RSS trigger with output capture
echo Running docketwatch_rss_trigger.py...
"C:\Program Files\Python312\python.exe" docketwatch_rss_trigger.py > logs\manual_rss_trigger_%timestamp%.log 2>&1

set exit_code=%errorlevel%

echo.
echo Exit code: %exit_code%
echo Execution completed at: %date% %time%

if %exit_code% neq 0 (
    echo ERROR: Script failed
    echo Check log file: logs\manual_rss_trigger_%timestamp%.log
    type logs\manual_rss_trigger_%timestamp%.log
) else (
    echo SUCCESS: Script completed
    echo Last few lines of output:
    powershell "Get-Content logs\manual_rss_trigger_%timestamp%.log | Select-Object -Last 10"
)

echo ========================================