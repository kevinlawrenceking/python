import subprocess
import time
import os
import signal

SCRAPER_SCRIPT = r"u:\docketwatch\python\docketwatch_pardons.py"

SLEEP_SECONDS = 200  # 10 minutes; change as needed

def run_scraper():
    try:
        print(f"Running: {SCRAPER_SCRIPT}")
        # Use sys.executable for full path to Python if needed
        proc = subprocess.Popen(["python", SCRAPER_SCRIPT])
        proc.wait()
        return proc.returncode
    except Exception as e:
        print(f"Error running scraper: {e}")
        return -1

def main():
    print("Starting scraper loop. Press Ctrl+C to exit.")
    while True:
        try:
            code = run_scraper()
            print(f"Scraper run finished with exit code {code}")
            print(f"Sleeping {SLEEP_SECONDS // 60} minutes before next run...")
            time.sleep(SLEEP_SECONDS)
        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as ex:
            print(f"Exception in loop: {ex}")
            print("Sleeping 1 minute before retry...")
            time.sleep(60)

if __name__ == "__main__":
    main()
