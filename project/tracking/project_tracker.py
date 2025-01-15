import logging
from ..utils.json_utils import JSONManager
from .window_tracker import WindowTracker

logger = logging.getLogger("custom_logger")

class ProjectTracker:
    def __init__(self, config):
        self.config = config
        self.logger = logger
        self.json_manager = JSONManager()
        self.window_tracker = WindowTracker()

    def determine_project(self):
        """Determine the current project based on window info and assigned projects."""
        latest_summary = self.json_manager.get_latest_summary(self.config["timesheets_dir"])

        if latest_summary:
            current_project = latest_summary.get("project_name")
            if current_project in self.config["assigned_projects"]:
                return current_project

        return "Bench - 0001"

    def determine_project_running(self):
        """Determine the current project based on window info and workspace paths."""
        window_info = self.window_tracker.get_active_window_info()
        if not window_info:
            return "Bench - 0001"

        process_name = window_info['process_name'].lower()
        window_title = window_info['window_title']

        if process_name in WindowTracker.IDE_PROCESSES:
            project_path = self.window_tracker.extract_project_path(window_title, window_info)
            if project_path:
                for project in self.config["assigned_projects"]:
                    if project.lower() in project_path.lower():
                        return project

        latest_summary = self.json_manager.get_latest_summary(self.config["timesheets_dir"])
        if latest_summary:
            project = latest_summary.get("project_name")
            if project in self.config["assigned_projects"]:
                return project

        return "Bench - 0001" 