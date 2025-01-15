import json
import logging
from datetime import datetime
import os

logger = logging.getLogger("custom_logger")

class JSONManager:
    def __init__(self):
        self.logger = logger

    def load_config(self, config_path):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            raise

    def save_daily_summary(self, summary_data, timesheets_dir):
        """Save daily summary to JSON file."""
        date_str = datetime.now().strftime("%Y%m%d")
        summary_file = os.path.join(timesheets_dir, f"summary_{date_str}.json")
        
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=4)
            return summary_file
        except Exception as e:
            self.logger.error(f"Error saving summary: {e}")
            return None

    def get_latest_summary(self, timesheets_dir):
        """Fetch the latest summary from the daily summary file."""
        date_str = datetime.now().strftime("%Y%m%d")
        daily_summary_file = os.path.join(timesheets_dir, f"summary_{date_str}.json")

        if os.path.exists(daily_summary_file):
            with open(daily_summary_file, "r", encoding="utf-8") as f:
                daily_data = json.load(f)
                if daily_data.get("summaries"):
                    return daily_data["summaries"][-1]
        return None
