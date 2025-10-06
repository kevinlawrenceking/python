@echo off
REM ================= UTF-8 environment and logging =================
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo =============================== >>u:\DOCKETWATCH\python\event_log.txt
echo START: %date% %time% summarize_document_event %1 >>u:\DOCKETWATCH\python\case_events_alert_log.txt

REM Pass through all arguments (doc_uid and options like --order=asc)
"C:\Program Files\Python312\python.exe" u:\DOCKETWATCH\python\summarize_document_event.py %* >>u:\DOCKETWATCH\python\case_events_alert_log.txt 2>&1

echo END: %date% %time% >>u:\DOCKETWATCH\python\event_log.txt
echo. >>u:\DOCKETWATCH\python\event_log.txt

exit /b 0
