import win32gui
import win32process
import psutil
import re
from pathlib import Path
import logging
import os

logger = logging.getLogger("custom_logger")

class WindowTracker:
    IDE_PROCESSES = {
        'code.exe': 'Visual Studio Code',
        'cursor.exe': 'Cursor',
        'pycharm64.exe': 'PyCharm',
        'idea64.exe': 'IntelliJ IDEA',
        'sublime_text.exe': 'Sublime Text',
        'atom.exe': 'Atom'
    }

    def __init__(self):
        self.logger = logger

    def get_active_window_info(self):
        """Gets detailed information about the current active window."""
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            process = psutil.Process(pid)
            window_title = win32gui.GetWindowText(hwnd)
            process_name = process.name()
            
            window_placement = win32gui.GetWindowPlacement(hwnd)
            is_minimized = window_placement[1] == 2
            is_maximized = window_placement[1] == 3
            
            return {
                'hwnd': hwnd,
                'window_title': window_title,
                'process_name': process_name,
                'executable_path': process.exe(),
                'creation_time': process.create_time(),
                'cpu_percent': process.cpu_percent(),
                'memory_info': process.memory_info()._asdict(),
                'status': process.status(),
                'username': process.username(),
                'command_line': process.cmdline(),
                'window_rect': win32gui.GetWindowRect(hwnd),
                'is_minimized': is_minimized,
                'is_maximized': is_maximized,
                'parent_process': process.parent().name() if process.parent() else None,
                'num_threads': process.num_threads(),
                'children': [child.name() for child in process.children()],
                'nice': process.nice(),
                'io_counters': process.io_counters()._asdict() if hasattr(process, 'io_counters') else None,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def is_browser_window(self, window_info):
        """Check if the current window is a browser."""
        if not window_info:
            return False
        
        browser_executables = [
            'chrome.exe', 'firefox.exe', 'msedge.exe', 
            'brave.exe', 'opera.exe', 'safari.exe'
        ]
        return window_info['process_name'].lower() in browser_executables

    def extract_project_path(self, window_title, window_info):
        """Extract project path from IDE window title."""
        try:
            vscode_pattern = r".*?(?:\s-\s)(.*?)(?:\s-\s.*Code)"
            
            cmd_line = window_info.get('command_line', [])
            for arg in cmd_line:
                if os.path.exists(arg) and os.path.isdir(arg):
                    return str(Path(arg).resolve())

            match = re.search(vscode_pattern, window_title)
            if match:
                potential_path = match.group(1).strip()
                full_path = str(Path(potential_path).resolve())
                if os.path.exists(full_path):
                    return full_path
            
            return None
        except Exception as e:
            self.logger.error(f"Error extracting project path: {e}")
            return None 