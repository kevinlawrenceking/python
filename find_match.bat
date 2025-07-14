@echo off
echo =============================== >> u:\docketwatch\python\event_log.txt
echo START: %date% %time% >> u:\docketwatch\python\find_match.txt

REM %1 is the first command-line argument (case_id)
"C:\Program Files\Python312\python.exe" u:\docketwatch\python\find_match.py %1 >> u:\docketwatch\python\case_events_alert_plus_log.txt 2>&1

echo END: %date% %time% >> u:\docketwatch\python\event_log.txt
echo. >> u:\docketwatch\python\event_log.txt

exit /b 0
