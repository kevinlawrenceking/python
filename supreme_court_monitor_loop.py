# supreme_court_monitor_loop.py
# Runs the Supreme Court monitor every 5 minutes in a continuous loop

import time
import subprocess
import os
import sys
import logging
from datetime import datetime

# Configuration
MONITOR_SCRIPT = "supreme_court_monitor.py"
SLEEP_MINUTES = 5
LOG_FILE = r"\\10.146.176.84\general\docketwatch\python\logs\supreme_court_monitor_loop.log"

# Logging setup
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_and_print(message):
    """Log to file and print to console"""
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    logging.info(message)

def run_monitor():
    """Run the Supreme Court monitor script"""
    script_path = os.path.join(os.path.dirname(__file__), MONITOR_SCRIPT)
    
    if not os.path.exists(script_path):
        log_and_print(f"ERROR: Monitor script not found at {script_path}")
        return False
    
    try:
        log_and_print("Starting Supreme Court monitor...")
        
        # Run the script and capture output
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            log_and_print("✅ Monitor completed successfully")
            if result.stdout:
                print("--- Monitor Output ---")
                print(result.stdout)
                print("--- End Output ---")
            return True
        else:
            log_and_print(f"❌ Monitor failed with return code {result.returncode}")
            if result.stderr:
                log_and_print(f"Error output: {result.stderr}")
                print(f"Error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_and_print("❌ Monitor script timed out after 5 minutes")
        return False
    except Exception as e:
        log_and_print(f"❌ Error running monitor: {e}")
        return False

def main():
    log_and_print("=" * 80)
    log_and_print("SUPREME COURT MONITOR LOOP STARTING")
    log_and_print(f"Will run monitor every {SLEEP_MINUTES} minutes")
    log_and_print("Press Ctrl+C to stop")
    log_and_print("=" * 80)
    
    run_count = 0
    
    try:
        while True:
            run_count += 1
            log_and_print(f"\n🔄 Starting monitor run #{run_count}")
            
            # Run the monitor
            success = run_monitor()
            
            if success:
                log_and_print(f"✅ Run #{run_count} completed successfully")
            else:
                log_and_print(f"❌ Run #{run_count} failed")
            
            # Sleep for 5 minutes
            log_and_print(f"😴 Sleeping for {SLEEP_MINUTES} minutes until next run...")
            log_and_print(f"Next run at: {datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=SLEEP_MINUTES)}")
            
            time.sleep(SLEEP_MINUTES * 60)  # Convert minutes to seconds
            
    except KeyboardInterrupt:
        log_and_print("\n🛑 Loop stopped by user (Ctrl+C)")
    except Exception as e:
        log_and_print(f"🚨 Fatal error in loop: {e}")
    
    log_and_print(f"Supreme Court Monitor Loop stopped after {run_count} runs")

if __name__ == "__main__":
    # Add missing import
    from datetime import timedelta
    main()
