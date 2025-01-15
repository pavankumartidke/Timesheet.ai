import os
from utils.logging_utils import LoggerSetup
from utils.file_utils import FileManager
from utils.json_utils import JSONManager
from tracking.work_tracker import WorkTracker
import threading
import schedule
import time

class TimeTracker:
    def __init__(self):
        self.logger = LoggerSetup.setup_logger()
        self.file_manager = FileManager()
        self.json_manager = JSONManager()
        self.config = None
        self.work_tracker = None

    def initialize(self):
        try:
            # Load configuration
            config_path = os.path.join("config", "config.json")
            self.config = self.json_manager.load_config(config_path)

            # Create absolute paths for directories
            base_dir = os.path.abspath(self.config["paths"]["base_dir"])
            directories = {
                "screenshot_dir": os.path.join(base_dir, self.config["paths"]["screenshot_dir"]),
                "logs_dir": os.path.join(base_dir, self.config["paths"]["logs_dir"]),
                "timesheets_dir": os.path.join(base_dir, self.config["paths"]["timesheets_dir"]),
                "excel_dir": os.path.join(base_dir, self.config["paths"]["excel_dir"])
            }

            # Update config with absolute paths
            self.config["paths"].update(directories)

            # Ensure required directories exist
            self.file_manager.ensure_directories(directories.values())

            # Initialize work tracker with updated config
            self.work_tracker = WorkTracker(self.config)
            
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            raise

    def start(self):
        try:
            # Start tracking threads
            self.work_tracker.tracking_active = True
            
            # Start work tracking thread
            work_thread = threading.Thread(
                target=self.work_tracker.track_work_time, 
                daemon=False
            )
            work_thread.start()

            # Start scheduler
            schedule.every(self.config["tracking"]["interval_minutes"]).minutes.do(
                self.work_tracker.run_task
            )
            
            # Keep main thread alive
            while True:
                schedule.run_pending()
                time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            self.work_tracker.tracking_active = False
            work_thread.join()
        except Exception as e:
            self.logger.error(f"Error in main: {e}")

def main():
    tracker = TimeTracker()
    tracker.initialize()
    tracker.start()

if __name__ == "__main__":
    main()
