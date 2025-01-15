import os
import json
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger("custom_logger")

class FileManager:
    def __init__(self):
        self.logger = logger

    def ensure_directories(self, dirs):
        """Ensure all required directories exist."""
        for directory in dirs:
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.debug(f"Directory ensured: {directory}")
            except Exception as e:
                self.logger.error(f"Error creating directory {directory}: {e}")

    def convert_summaries_to_excel(self, json_file_path, excel_output_path):
        """Convert JSON summaries to Excel with directory creation."""
        try:
            excel_dir = os.path.dirname(excel_output_path)
            os.makedirs(excel_dir, exist_ok=True)
            
            with open(json_file_path, 'r') as file:
                data = json.load(file)
            
            summaries = data.get('summaries', [])
            total_work_time_hours = data.get('total_work_time_hours', 0)
            project_times = data.get('project_times', {})

            summary_row = {
                "software_used": "",
                "job_name": "",
                "project_name": "",
                "work_items": "",
                "description": "",
                "time_spent": "",
                "image_url": "",
                "Total_worked_time_hours": total_work_time_hours
            }

            for project, time in project_times.items():
                summary_row[project] = time

            all_rows = [summary_row]

            for summary in summaries:
                detailed_row = {
                    "software_used": summary.get("software_used", ""),
                    "job_name": summary.get("job_name", ""),
                    "project_name": summary.get("project_name", ""),
                    "work_items": summary.get("work_items", ""),
                    "description": "; ".join(summary.get("description", [])) if isinstance(summary.get("description"), list) else summary.get("description", ""),
                    "time_spent": summary.get("time_spent", ""),
                    "image_url": summary.get("image_url", "")
                }
                all_rows.append(detailed_row)

            df = pd.DataFrame(all_rows)
            df.to_excel(excel_output_path, index=False, engine='openpyxl')
            self.logger.info(f"Excel file created successfully at {excel_output_path}")
            
        except Exception as e:
            self.logger.error(f"Error converting to Excel: {e}")
