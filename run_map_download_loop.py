import subprocess
import time
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('u:\\docketwatch\\python\\logs\\map_download_loop.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Configuration
SCRIPT_PATH = "u:\\docketwatch\\python\\download_map_pdfs.py"
LOOP_DELAY_SECONDS = 300  # 5 minutes between runs
MAX_CONSECUTIVE_FAILURES = 5

def run_map_download():
    """Run the MAP PDF download script and return success status."""
    try:
        logger.info("Starting MAP PDF download script...")
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode == 0:
            logger.info("MAP PDF download script completed successfully")
            if result.stdout:
                logger.info(f"Script output: {result.stdout}")
            return True
        else:
            logger.error(f"MAP PDF download script failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Script error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("MAP PDF download script timed out after 1 hour")
        return False
    except Exception as e:
        logger.error(f"Exception running MAP PDF download script: {e}")
        return False

def main():
    """Main loop to continuously run the MAP PDF download script."""
    logger.info("Starting MAP PDF download loop...")
    consecutive_failures = 0
    
    try:
        while True:
            start_time = datetime.now()
            success = run_map_download()
            end_time = datetime.now()
            duration = end_time - start_time
            
            if success:
                consecutive_failures = 0
                logger.info(f"Run completed successfully in {duration}")
            else:
                consecutive_failures += 1
                logger.warning(f"Run failed (consecutive failures: {consecutive_failures})")
                
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(f"Too many consecutive failures ({consecutive_failures}). Stopping loop.")
                    break
            
            logger.info(f"Waiting {LOOP_DELAY_SECONDS} seconds before next run...")
            time.sleep(LOOP_DELAY_SECONDS)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Stopping loop...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("MAP PDF download loop stopped.")

if __name__ == "__main__":
    main()
