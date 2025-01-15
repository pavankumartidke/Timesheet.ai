import time
import ctypes
import win32api
import logging
from threading import Lock
from datetime import datetime
from ..utils.json_utils import save_daily_summary

logger = logging.getLogger("custom_logger")

class WorkTracker:
    def __init__(self, config):
        self.config = config
        self.tracking_active = False
        self.work_start_time = None
        self.total_work_seconds = 0
        self.current_project_times = {}
        self.inactivity_start_time = None
        self.file_lock = Lock()

    def is_system_locked(self):
        """Check if the system is locked."""
        user32 = ctypes.windll.User32
        return user32.GetForegroundWindow() == 0

    def track_work_time(self):
        """Track total work time and update project times."""
        try:
            while self.tracking_active:
                time.sleep(1)

                if self.is_system_locked():
                    logger.info("System is locked. Triggering daily work summary save.")
                    self.save_daily_work_summary()
                    continue

                last_input_info = win32api.GetLastInputInfo()
                idle_time = (win32api.GetTickCount() - last_input_info) / 1000.0

                if idle_time >= self.config["inactivity_threshold"]:
                    if self.inactivity_start_time is None:
                        self.inactivity_start_time = time.time()
                        logger.debug(f"Inactivity detected. Starting timer... (Idle for {idle_time:.1f} seconds)")
                    elif time.time() - self.inactivity_start_time >= self.config["inactivity_threshold"]:
                        logger.info(f"Inactivity threshold exceeded ({idle_time:.1f} seconds). Triggering daily work summary save.")
                        self.save_daily_work_summary()
                        continue
                else:
                    if self.inactivity_start_time is not None:
                        logger.debug("Activity detected. Resetting inactivity timer.")
                        self.inactivity_start_time = None

                if self.work_start_time is None:
                    self.work_start_time = time.time()
                self.total_work_seconds += 1

                from .project_tracker import determine_project
                project_name = determine_project(self.config)
                if project_name not in self.current_project_times:
                    self.current_project_times[project_name] = 0
                self.current_project_times[project_name] += 1

        except Exception as e:
            logger.error(f"Error in work time tracking: {e}")
        finally:
            logger.info("Tracking stopped. Saving final summary.")
            self.save_daily_work_summary()

    def save_daily_work_summary(self):
        """Save the daily work summary with total work time and project details."""
        if self.total_work_seconds == 0:
            logger.debug("No work logged. Skipping save.")
            return

        new_data = {
            "total_work_time_hours": round(self.total_work_seconds / 3600, 2),
            "project_times": {
                project: round(seconds / 3600, 2) 
                for project, seconds in self.current_project_times.items()
            }
        }

        save_daily_summary(new_data, self.config["timesheets_dir"])

        self.total_work_seconds = 0
        self.current_project_times = {}
        self.work_start_time = None 