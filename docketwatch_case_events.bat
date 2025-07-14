@echo off
echo =============================== >>u:\DOCKETWATCH\python\event_log.txt
echo START: %date% %time% >>u:\DOCKETWATCH\python\event_log.txt

"C:\Program Files\Python312\python.exe" u:\DOCKETWATCH\python\docketwatch_case_events.py >>u:\DOCKETWATCH\python\event_log.txt 2>&1

echo END: %date% %time% >>u:\DOCKETWATCH\python\event_log.txt
echo. >>u:\DOCKETWATCH\python\event_log.txt

exit /b 0
