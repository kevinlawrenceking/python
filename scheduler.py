from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess
from datetime import datetime

# Define your script location
script_path = r"\\10.146.176.84\general\docketwatch\python\script.py"

# Function to run the Python script
def run_script():
    print(f"Running script at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    subprocess.run([r"\\10.146.176.84\general\docketwatch\python\python.exe", script_path], check=True)

# Initialize the scheduler
scheduler = BlockingScheduler()

# Schedule the script to run at :04 and :08 of each hour from 9 AM to 4 PM
scheduler.add_job(run_script, 'cron', hour="9-16", minute="4,8")

# Additional jobs for 5:04 PM and 5:08 PM
scheduler.add_job(run_script, 'cron', hour=17, minute=4)
scheduler.add_job(run_script, 'cron', hour=17, minute=8)

print("Scheduler started. Running at :04 and :08 of each hour from 9 AM to 5 PM.")
scheduler.start()
