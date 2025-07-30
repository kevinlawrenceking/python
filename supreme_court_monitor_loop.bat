@echo off
echo Starting Supreme Court Monitor Loop...
echo This will run the monitor every 5 minutes
echo Press Ctrl+C to stop

cd /d "u:\docketwatch\python"
python supreme_court_monitor_loop.py

pause
