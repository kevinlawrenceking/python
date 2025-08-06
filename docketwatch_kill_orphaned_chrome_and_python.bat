@echo off
setlocal

:: Define log file path (modify this if needed)
set LOGFILE=%~dp0logs\chrome_cleanup.log

:: Create logs folder if it doesn't exist
if not exist "%~dp0logs" (
    mkdir "%~dp0logs"
)

:: Get current datetime
for /f %%i in ('powershell -Command "Get-Date -Format yyyy-MM-dd_HH:mm:ss"') do set timestamp=%%i

echo [%timestamp%] Starting Chrome and Python cleanup >> "%LOGFILE%"
echo Killing orphaned Chrome and Python processes...

:: Kill background ChromeDriver processes
for /f "tokens=2 delims=," %%A in ('tasklist /FI "IMAGENAME eq chromedriver.exe" /FO CSV /NH') do (
    echo [%timestamp%] Terminating ChromeDriver PID: %%A >> "%LOGFILE%"
    taskkill /PID %%A /F >> "%LOGFILE%" 2>&1
)

:: Kill background Chrome processes likely from Selenium (non-visible)
for /f "tokens=2 delims=," %%A in ('tasklist /FI "IMAGENAME eq chrome.exe" /FO CSV /NH') do (
    echo [%timestamp%] Terminating Chrome PID: %%A >> "%LOGFILE%"
    taskkill /PID %%A /F >> "%LOGFILE%" 2>&1
)

:: Kill python processes that are likely stale (>60 mins old)
echo [%timestamp%] Checking for long-running Python processes... >> "%LOGFILE%"
powershell -Command ^
    "Get-Process python | Where-Object { $_.StartTime -lt (Get-Date).AddMinutes(-60) } | ForEach-Object { ^
        Add-Content -Path '%LOGFILE%' -Value ('[%s] Killing Python PID: ' -f (Get-Date -Format 'yyyy-MM-dd_HH:mm:ss') + $_.Id); ^
        Stop-Process -Id $_.Id -Force }" >> "%LOGFILE%" 2>&1

echo [%timestamp%] Cleanup done. >> "%LOGFILE%"
echo Done.

endlocal
