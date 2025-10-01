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
for /f "tokens=2 delims=," %%A in ('tasklist /FI "IMAGENAME eq chromedriver.exe" /FO CSV /NH 2^>nul') do (
    for /f %%i in ('powershell -Command "Get-Date -Format yyyy-MM-dd_HH:mm:ss"') do set timestamp=%%i
    echo [%timestamp%] Terminating ChromeDriver PID: %%A >> "%LOGFILE%"
    taskkill /PID %%A /F >> "%LOGFILE%" 2>&1
)

:: Kill background Chrome processes likely from Selenium (non-visible)
for /f "tokens=2 delims=," %%A in ('tasklist /FI "IMAGENAME eq chrome.exe" /FO CSV /NH 2^>nul') do (
    for /f %%i in ('powershell -Command "Get-Date -Format yyyy-MM-dd_HH:mm:ss"') do set timestamp=%%i
    echo [%timestamp%] Terminating Chrome PID: %%A >> "%LOGFILE%"
    taskkill /PID %%A /F >> "%LOGFILE%" 2>&1
)

:: Kill python processes that are likely stale (>60 mins old)
for /f %%i in ('powershell -Command "Get-Date -Format yyyy-MM-dd_HH:mm:ss"') do set timestamp=%%i
echo [%timestamp%] Checking for long-running Python processes... >> "%LOGFILE%"
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -lt (Get-Date).AddMinutes(-60) } | ForEach-Object { Write-Host \"Killing Python PID: $($_.Id)\"; Stop-Process -Id $_.Id -Force }" >> "%LOGFILE%" 2>&1

for /f %%i in ('powershell -Command "Get-Date -Format yyyy-MM-dd_HH:mm:ss"') do set timestamp=%%i
echo [%timestamp%] Cleanup done. >> "%LOGFILE%"
echo Done.

endlocal
