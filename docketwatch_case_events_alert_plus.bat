@echo off
echo =============================== >> u:\DOCKETWATCH\python\event_log.txt
echo START: %date% %time% >> u:\DOCKETWATCH\python\case_events_alert_plus_log.txt

REM %1 is the first command-line argument (case_id)
"C:\Program Files\Python312\python.exe" u:\DOCKETWATCH\python\docketwatch_case_events_alert_plus.py %1 >> u:\DOCKETWATCH\python\case_events_alert_plus_log.txt 2>&1

echo END: %date% %time% >> u:\DOCKETWATCH\python\event_log.txt
echo. >> u:\DOCKETWATCH\python\event_log.txt

exit /b 0
