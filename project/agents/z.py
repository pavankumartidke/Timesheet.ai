import os
import time
import threading
import schedule
import pyautogui
from datetime import datetime
import win32gui
import win32process
import psutil
import pandas as pd
from openai import OpenAI
import json
import base64
from collections import defaultdict
import ctypes
from threading import Lock
import pytesseract
import re
from pathlib import Path
import logging
import colorlog
import win32api

#parallel agents, look and understand the threading and scheduling and how to optimize it

# Load configuration
EXCEL_DIR = "excel"
EXCEL_PATH = os.path.join(os.path.dirname(__file__), EXCEL_DIR)
excel_output_path = os.path.join(EXCEL_PATH, "TimeSheet.xlsx")

file_lock = Lock()
CONFIG = json.load(open("config.json"))
OPENAI_API_KEY = CONFIG["openai_api_key"]
INACTIVITY_THRESHOLD = CONFIG["inactivity_threshold"]
TRACKING_INTERVAL = CONFIG["interval_minutes"]
WINDOW_SWITCH_INTERVAL = CONFIG["window_switch_interval"]
ASSIGNED_PROJECTS = CONFIG["assigned_projects"]
SCREENSHOT_DIR = "screenshots"
LOGS_DIR = "logs"
TIMESHEETS_DIR = "timeSheets"
GPT_MODEL = "gpt-4o"
SYSTEM_PROMPT = """
    You are a productivity assistant. Your task is to:
    1. Analyze the provided JSON input and extract actionable tasks and activities.
    2. For project identification, use the following mapping rules:
       - If you see folder name '{folder_mappings}', assign it to corresponding project.
       - Only use project names from the approved list: {assigned_projects}
       - If uncertain, use 'Review Needed'
    3. For work items, only use the allowed items for the identified project:
       {project_work_items}
    4. Organize the information into a structured JSON format.
    5. Don't return any other text than the JSON.
    6. Ensure the JSON includes the following fields:
       - software_used: The software, application, or window identified.
       - job_name: The name of the job being worked on like designing, coding, emailing, searching, etc.
       - project_name: The name or context of the project being worked on or if in any online meeting.
       - work_items: MUST be from the allowed work items for the identified project.
       - description: A list of items, actions, or subtasks related to the task.
       - time: current time of the current session.
       - image_url: The URL of the image associated with this analysis.
    """
IDE_PROCESSES = {
    'code.exe': 'Visual Studio Code',
    'cursor.exe': 'Cursor',
    'pycharm64.exe': 'PyCharm',
    'idea64.exe': 'IntelliJ IDEA',
    'sublime_text.exe': 'Sublime Text',
    'atom.exe': 'Atom'
}


# logger setup
# Create a handler with a colored formatter
# Custom color for time (in hex: #00afd7)
TIME_COLOR = '\033[38;2;0;175;215m'  # RGB for #00afd7
RESET_COLOR = '\033[0m'  # Reset color

# Create a StreamHandler with a colored formatter
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "[%(asctime)s]  %(log_color)s[%(levelname)s]%(reset)s %(log_color)s%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

# Customizing the time format manually
class CustomFormatter(colorlog.ColoredFormatter):
    def format(self, record):
        log_message = super().format(record)
        # Add the custom color for time and reset after
        log_message = log_message.replace(f"[{record.asctime}]", f"{TIME_COLOR}[{record.asctime}]{RESET_COLOR}")
        return log_message

# Create logger
logger = logging.getLogger("custom_logger")
logger.setLevel(logging.DEBUG)
handler.setFormatter(CustomFormatter(
    "[%(asctime)s]  %(log_color)s[%(levelname)s]%(reset)s %(log_color)s%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

logger.addHandler(handler)

# Log messages
# logger.debug("This is a DEBUG message.")
# logger.info("This is an INFO message.")
# logger.warning("This is a WARNING message.")
# logger.error("This is an ERROR message.")
# logger.critical("This is a CRITICAL message.")


# Ensure necessary directories exist
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TIMESHEETS_DIR, exist_ok=True)

# Initialize OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

# Global tracking state
tracking_active = False
previous_window_title = None
last_window_switch_time = 0
window_switch_lock = threading.Lock()


#2nd try for time
work_start_time = None
total_work_seconds = 0
current_project_times = {}
inactivity_start_time = None

def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        SCREENSHOT_DIR,
        LOGS_DIR,
        TIMESHEETS_DIR,
        EXCEL_PATH  # Add Excel directory
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"Directory ensured: {directory}")
        except Exception as e:
            logger.error(f"Error creating directory {directory}: {e}")

def convert_summaries_to_excel(json_file_path, excel_output_path):
    """Convert JSON summaries to Excel with directory creation."""
    try:
        # Ensure Excel directory exists
        excel_dir = os.path.dirname(excel_output_path)
        os.makedirs(excel_dir, exist_ok=True)
        
        # Read the JSON file
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        
        # Extract summaries and other required data
        summaries = data.get('summaries', [])
        total_work_time_hours = data.get('total_work_time_hours', 0)
        project_times = data.get('project_times', {})

        # Prepare the first row with summary-level data
        summary_row = {
            "software_used": "",
            "job_name": "",
            "project_name": "",
            "work_items": "",
            "description": "",
            "time_spent": "",
            "image_url": ""
        }

        # Add project times as new columns to the summary row
        summary_row["Total_worked_time_hours"] = total_work_time_hours
        for project, time in project_times.items():
            summary_row[project] = time

        # Create a list to store all rows
        all_rows = [summary_row]

        # Process each detailed summary and add to the list
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

        # Convert to DataFrame
        df = pd.DataFrame(all_rows)

        # Save to Excel
        df.to_excel(excel_output_path, index=False, engine='openpyxl')
        logger.info(f"Excel file created successfully at {excel_output_path}")
        
    except FileNotFoundError:
        logger.error(f"JSON file not found: {json_file_path}")
    except PermissionError:
        logger.error(f"Permission denied when writing to Excel file: {excel_output_path}")
    except Exception as e:
        logger.error(f"Error converting to Excel: {e}")

def is_system_locked():
    """Check if the system is locked."""
    user32 = ctypes.windll.User32
    return user32.GetForegroundWindow() == 0

def determine_project():
    """Determine the current project based on window info and assigned projects."""
    # Check the assigned projects in the last recorded summary file
    latest_summary = get_latest_summary()

    # If a project is already identified, we use it
    if latest_summary:
        current_project = latest_summary.get("project_name")
        # Verify if the project is still in assigned projects
        if current_project in CONFIG["assigned_projects"]:
            return current_project

    # If no valid project is found, return the bench project
    return "Bench - 0001"

def determine_project_running():
    """Determine the current project based on window info and workspace paths."""
    window_info = get_active_window_info()
    if not window_info:
        return "Bench - 0001"

    process_name = window_info['process_name'].lower()
    window_title = window_info['window_title']

    # Check if current process is an IDE
    if process_name in IDE_PROCESSES:
        # Extract project path from window title
        project_path = extract_project_path(window_title, window_info)
        if project_path:
            # Try to match project path with assigned projects
            for project in CONFIG["assigned_projects"]:
                if project.lower() in project_path.lower():
                    return project

    # Fallback to existing summary check
    latest_summary = get_latest_summary()
    if latest_summary:
        project = latest_summary.get("project_name")
        if project in CONFIG["assigned_projects"]:
            return project

    return "Bench - 0001"

def extract_project_path(window_title, window_info):
    """Extract project path from IDE window title."""
    try:
        # VSCode/Cursor pattern: "filename - folder - Visual Studio Code"
        vscode_pattern = r".*?(?:\s-\s)(.*?)(?:\s-\s.*Code)"
        
        # Try to get from command line arguments first
        cmd_line = window_info.get('command_line', [])
        for arg in cmd_line:
            if os.path.exists(arg) and os.path.isdir(arg):
                return str(Path(arg).resolve())

        # Try to extract from window title
        match = re.search(vscode_pattern, window_title)
        if match:
            potential_path = match.group(1).strip()
            # Convert to absolute path if possible
            full_path = str(Path(potential_path).resolve())
            if os.path.exists(full_path):
                return full_path

        # Additional IDE-specific patterns can be added here
        
        return None
    except Exception as e:
        logger.error(f"Error extracting project path: {e}")
        return None

def get_latest_summary():

    """Fetch the latest summary from the daily summary file."""
    # Assuming the timestamp from window_info is available
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S").split("_")[0]
    daily_summary_file = os.path.join(TIMESHEETS_DIR, f"summary_{date_str}.json")

    if os.path.exists(daily_summary_file):
        with open(daily_summary_file, "r", encoding="utf-8") as f:
            daily_data = json.load(f)
            if daily_data.get("summaries"):
                # Get the last summary in the list
                return daily_data["summaries"][-1]
    return None
def track_work_time():
    """Track total work time and update project times."""
    global work_start_time, total_work_seconds, inactivity_start_time
    try:
        while tracking_active:
            time.sleep(1)  # Monitor every second

            # Check for system lock first
            if is_system_locked():
                logger.info("System is locked. Triggering daily work summary save.")
                save_daily_work_summary()
                continue

            # Get last input time using win32api
            last_input_info = win32api.GetLastInputInfo()
            idle_time = (win32api.GetTickCount() - last_input_info) / 1000.0  # Convert to seconds

            # Check for inactivity
            if idle_time >= INACTIVITY_THRESHOLD:
                if inactivity_start_time is None:
                    inactivity_start_time = time.time()
                    logger.debug(f"Inactivity detected. Starting timer... (Idle for {idle_time:.1f} seconds)")
                elif time.time() - inactivity_start_time >= INACTIVITY_THRESHOLD:
                    logger.info(f"Inactivity threshold exceeded ({idle_time:.1f} seconds). Triggering daily work summary save.")
                    save_daily_work_summary()
                    continue
            else:
                # Reset inactivity tracker on activity
                if inactivity_start_time is not None:
                    logger.debug("Activity detected. Resetting inactivity timer.")
                    inactivity_start_time = None

            # Update total work time
            if work_start_time is None:
                work_start_time = time.time()
            total_work_seconds += 1

            # Update per-project tracking
            project_name = determine_project()
            if project_name not in current_project_times:
                current_project_times[project_name] = 0
            current_project_times[project_name] += 1

    except Exception as e:
        logger.error(f"Error in work time tracking: {e}")
    finally:
        # Ensure data is saved when tracking stops
        logger.info("Tracking stopped. Saving final summary.")
        save_daily_work_summary()
        save_daily_work_summary()

def save_daily_work_summary():
    """Save the daily work summary with total work time and project details."""
    global total_work_seconds, current_project_times, work_start_time

    if total_work_seconds == 0:
        logger.debug("No work logged. Skipping save.")
        return

    # Prepare the new data to be added
    new_data = {
        "total_work_time_hours": round(total_work_seconds / 3600, 2),
        "project_times": {
            project: round(seconds / 3600, 2) for project, seconds in current_project_times.items()
        }
    }

    # Save the summary to the timesheets folder
    date_str = datetime.now().strftime("%Y%m%d")
    summary_file = os.path.join(TIMESHEETS_DIR, f"summary_{date_str}.json")

    if os.path.exists(summary_file):
        # Load existing data
        with open(summary_file, "r", encoding="utf-8") as f:
            daily_data = json.load(f)
    else:
        # Initialize new data if file doesn't exist
        daily_data = {"date": datetime.now().strftime("%Y-%m-%d"), "summaries": []}

    # Update or add to existing fields
    if "total_work_time_hours" in daily_data:
        daily_data["total_work_time_hours"] += new_data["total_work_time_hours"]
    else:
        daily_data["total_work_time_hours"] = new_data["total_work_time_hours"]

    if "project_times" in daily_data:
        for project, time in new_data["project_times"].items():
            if project in daily_data["project_times"]:
                daily_data["project_times"][project] += time
            else:
                daily_data["project_times"][project] = time
    else:
        daily_data["project_times"] = new_data["project_times"]

    # Write the updated JSON back to the file
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, indent=4)

    # logger.info(f"Daily work summary saved to: {summary_file}")

    convert_summaries_to_excel(summary_file, excel_output_path)

    # Reset tracking variables
    total_work_seconds = 0
    current_project_times = {}
    work_start_time = None


def get_active_window_info():
    """Gets detailed information about the current active window."""
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        process = psutil.Process(pid)
        window_title = win32gui.GetWindowText(hwnd)
        process_name = process.name()
        
        # Get window state using GetWindowPlacement
        window_placement = win32gui.GetWindowPlacement(hwnd)
        # showCmd value: 1 = normal, 2 = minimized, 3 = maximized
        is_minimized = window_placement[1] == 2
        is_maximized = window_placement[1] == 3
        
        return {
            'hwnd': hwnd,
            'window_title': window_title,
            'process_name': process_name,
            'executable_path': process.exe(),
            # New detailed information
            'creation_time': process.create_time(),
            'cpu_percent': process.cpu_percent(),
            'memory_info': process.memory_info()._asdict(),
            'status': process.status(),
            'username': process.username(),
            'command_line': process.cmdline(),
            'window_rect': win32gui.GetWindowRect(hwnd),  # (left, top, right, bottom)
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


def is_browser_window(window_info):
    """Check if the current window is a browser."""
    if not window_info:
        return False
    
    browser_executables = [
        'chrome.exe', 'firefox.exe', 'msedge.exe', 
        'brave.exe', 'opera.exe', 'safari.exe'
    ]
    return window_info['process_name'].lower() in browser_executables

def check_window_change():
    """Check for window changes and trigger screenshot if needed."""
    global previous_window_title, last_window_switch_time
    
    if not tracking_active:
        return

    current_window_info = get_active_window_info()
    
    if current_window_info:
        current_window_title = current_window_info.get('window_title', '')
        
        # More robust comparison, handle None cases
        if (current_window_title and 
            current_window_title != previous_window_title):
            current_time = time.time()
            
            # Debounce mechanism: wait few seconds between screenshots
            with window_switch_lock:
                if current_time - last_window_switch_time >= WINDOW_SWITCH_INTERVAL:
                    try:
                        logger.debug(f"Window changed to: {current_window_title} ({current_window_info.get('process_name', 'Unknown')})")
                        
                        # Additional check for browser tabs
                        if is_browser_window(current_window_info):
                            logger.debug("Browser window detected. Taking screenshot...")
                        
                        # Capture screenshot
                        run_task()
                        
                        # Update tracking variables
                        previous_window_title = current_window_title
                        last_window_switch_time = current_time
                    except Exception as e:
                        logger.error(f"Error in window change tracking: {e}")

def capture_screen(timestamp):
    """Captures a screenshot of the current screen."""
    file_path = os.path.join(SCREENSHOT_DIR, f"screenshot_{timestamp}.png")
    pyautogui.screenshot(file_path)
    return file_path

def encode_image(image_path):
        """Convert a local image file to a Base64-encoded string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
        
def extract_text_from_image(image_path):
    """Sends the image to the Vision model to extract text."""
    with open(image_path, "rb") as image_file:
        # image_data = base64.b64encode(image_file.read()).decode("utf-8")
        image_data = f"data:image/jpeg;base64,{encode_image(image_path)}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                
                        "Step 1: Extract all text visible in the image as plain text. "
                        "Do not summarize or interpret it; just provide a raw JSON value.\n"
                        "Step 2: Provide a detailed each and very minute details and analysis of the image, including:\n"
                        "- All objects present, their work, and their relationships with each other.\n"
                        "- Scene context (what is happening, environment, capture all minor details, etc.).\n"
                        "- Identify any software, window, or tab visible, and which project it is for.\n\n"
                        "Format the response as a structured JSON object with the following format:\n"
                        "{\n"
                        "  'ocr_text': '<all extracted text>',\n"
                        "  'details': {\n"
                        "    'objects': '<list of detected objects and their detailed description related to the scene>',\n"
                        "    'scene_context': '<detailed minutes level description of the scene>',\n"
                        "    'software_identification': '<name of software/window/tab, if identifiable>',\n"
                        "    'project_context': '<details about the project, if inferable>'\n"
                        "  }\n"
                        "}\n\n"
                        "Constraints:\n"
                        "- The output must be valid JSON, and no extraneous text, commentary, or explanations should be included.\n"
                        "- Be concise and accurate, returning only the JSON object.\n\n"),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data, "detail": "high"},
                        },
                    ],
                }
            ],
            temperature=0,
            max_tokens=1000,
        )
            # Extracting the text response
        text_response = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()

        return text_response
    
    
    except Exception as e:
        logger.error(f"Error with Vision model: {e}")
        return "Error extracting text."

def extract_text_from_image_tess(image_path):
    """Extract text from an image using Tesseract OCR."""

    # OCR with tesseract
    # Set the path to Tesseract if not added to PATH
    pytesseract.pytesseract.tesseract_cmd = r'C:\IDXPROJT\AI\Browser-use\Timesheet_test\Tesseract\tesseract.exe'


    try:
        text = pytesseract.image_to_string(image_path)
        logger.debug("\nExtracted Text:")
        logger.debug(text)
        return text
    except Exception as e:
        logger.error(f"Error during OCR: {e}")
        return None

def log_extracted_text(text, timestamp):
    """Logs the extracted text to the logs folder."""
    log_file = os.path.join(LOGS_DIR, f"log_{timestamp}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(text)
    return log_file


def summarize_text(text, timestamp, screenshot_path):
    """Summarizes the extracted text using GPT with project-specific work items."""
    try:
        absolute_screenshot_path = os.path.abspath(screenshot_path)
        
        # Get current project
        current_project = determine_project()
        
        # Get work items for the current project
        work_items = CONFIG["assigned_projects"].get(current_project, {}).get("work_item", [])
        if not work_items and current_project == "Bench - 0001":
            # Use default work items for bench project if none specified
            work_items = ["Time", "Searching", "Training"]
            
        # Format projects and work items for the prompt
        assigned_projects_str = ", ".join(f'"{project}"' for project in CONFIG["assigned_projects"].keys())
        work_items_str = ", ".join(f'"{item}"' for item in work_items)
        
        project_assignment_prompt = (
            f"The user has the following assigned projects: [{assigned_projects_str}]. "
            f"For the current project '{current_project}', the available work items are: [{work_items_str}]. "
            "Based on the screenshot content, strictly follow these rules to provide your response:\n"
            "1. Assign the task to exactly one project from the provided list of projects. "
            "   If the task does not clearly belong to any project, assign it to 'Bench - 0001'.\n"
            "2. Assign the task to exactly one work item from the work items available for the identified project. "
            "   For 'Bench - 0001', use one of: Time, Searching, or Training."
        )
        
        combined_prompt = SYSTEM_PROMPT + "\n\n" + project_assignment_prompt
        
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": combined_prompt},
                {"role": "user", "content": f"Analyze the following JSON and summarize it for a timesheet: \n\n{text}. For the image_url field, provide the screenshot path: {absolute_screenshot_path} and for the current timestamp field, provide the timestamp: {timestamp}"}
            ],
            max_tokens=1000,
            temperature=0
        )
        
        # Get response content and validate JSON
        response_content = response.choices[0].message.content
        response_content = response_content.replace("```json", "").replace("```", "").strip()
        
        # Validate the response is valid JSON before returning
        json.loads(response_content)  # Test if it's valid JSON
        return response_content
        
    except json.JSONDecodeError as e:
        logger.error(f"GPT response is not valid JSON: {e}")
        logger.error(f"Raw GPT response from Except: {response_content}")
        return json.dumps({
            "software_used": "N/A",
            "job_name": "Error",
            "project_name": "Bench - 0001",
            "work_items": "Time",
            "description": ["Error: Invalid JSON response from GPT"],
            "time_spent": "0",
            "image_url": absolute_screenshot_path
        })
    except Exception as e:
        logger.error(f"Error with GPT: {e}")
        return json.dumps({
            "software_used": "N/A",
            "job_name": "Error",
            "project_name": "Bench - 0001",
            "work_items": "Time",
            "description": [f"Error: {str(e)}"],
            "time_spent": "0",
            "image_url": absolute_screenshot_path
        })

def save_summary(summary, timestamp):
    """Saves the summary to the timesheets folder."""
    date_str = timestamp.split("_")[0]  # Format: YYYYMMDD
    Timestamp = datetime.now().strftime("%Y-%m-%d")
    daily_summary_file = os.path.join(TIMESHEETS_DIR, f"summary_{date_str}.json")

    if os.path.exists(daily_summary_file):
        with open(daily_summary_file, "r", encoding="utf-8") as f:
            daily_data = json.load(f)
    else:
        daily_data = {"date": Timestamp, "summaries": []}
    
    try:
        # Handle empty or None summary
        if not summary:
            logger.warning("Empty summary received")
            return None
            
        # Parse summary if it's a string
        if isinstance(summary, str):
            try:
                summary_json = json.loads(summary)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode summary JSON: {e}")
                return None
        else:
            summary_json = summary

        # Handle case where summary_json is a list
        if isinstance(summary_json, list):
            logger.warning("Received list instead of dict, using first item")
            if not summary_json:  # Empty list
                return None
            summary_json = summary_json[0] if isinstance(summary_json[0], dict) else {
                "software_used": "N/A",
                "job_name": "Error",
                "project_name": "Bench - 0001",
                "work_items": "Time",
                "description": ["Error: Invalid data format"],
                "time_spent": "0",
                "timestamp": timestamp
            }

        # Ensure we have a dictionary
        if not isinstance(summary_json, dict):
            logger.warning(f"Invalid summary format: {type(summary_json)}")
            summary_json = {
                "software_used": "N/A",
                "job_name": "Error",
                "project_name": "Bench - 0001",
                "work_items": "Time",
                "description": ["Error: Invalid data type"],
                "time_spent": "0",
                "timestamp": timestamp
            }

        # Validate project name and set to Bench if not in assigned projects
        if not summary_json.get("project_name") or summary_json["project_name"] not in CONFIG["assigned_projects"]:
            summary_json["project_name"] = "Bench - 0001"
            
        daily_data["summaries"].append(summary_json)
        
        # Save the updated data
        with open(daily_summary_file, "w", encoding="utf-8") as f:
            json.dump(daily_data, f, indent=4)
            
        logger.info(f"Current summary saved")
        return daily_summary_file
        
    except Exception as e:
        logger.error(f"Unexpected error processing summary: {e}")
        logger.error(f"Summary content: {summary}")
        return None

def run_task():
    """Handles the main task: capture screenshot, extract text, and summarize."""
    # Capture a screenshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = capture_screen(timestamp)
    # logger.debug(f"Screenshot saved line no 710: {screenshot_path}")   
    logger.info(f"Screenshot captured")

    # Extract text from the screenshot
    extracted_text = extract_text_from_image(screenshot_path)
    

    log_file = log_extracted_text(extracted_text, timestamp)
    # logger.debug(f"Extracted text logged: {log_file}")
    logger.info(f"Log file generated")

    # Summarize the extracted text
    summary = summarize_text(extracted_text, timestamp, screenshot_path)
    # print('SUMMARY => ', summary)
    summary_file = save_summary(summary, timestamp)
    # logger.debug(f"Summary saved: {summary_file}")

def window_change_monitor():
    """Continuously monitor window changes in a separate thread."""
    global tracking_active
    while tracking_active:
        # print("Monitoring window changes...")  # Added logging
        check_window_change()
        time.sleep(1)  # Check every second

def scheduler_loop():
    """Runs the scheduler loop in a separate thread."""
    while tracking_active:
        schedule.run_pending()
        time.sleep(1)


def start_tracking():
    """Starts the tracking process."""
    global tracking_active
    if not tracking_active:
        tracking_active = True

        # Start work tracking thread
        work_tracker_thread = threading.Thread(target=track_work_time, daemon=False)
        work_tracker_thread.start()

        # Start window change monitoring thread
        window_monitor_thread = threading.Thread(target=window_change_monitor, daemon=False)
        window_monitor_thread.start()

        schedule.every(TRACKING_INTERVAL).minutes.do(run_task)
        threading.Thread(target=scheduler_loop, daemon=True).start()
        logger.info("Tracking started.")


def stop_tracking():
    """Stops the tracking process."""
    global tracking_active
    if tracking_active:
        tracking_active = False
        schedule.clear()
        print("Tracking stopped.")


# Testing endpoints if needed
if __name__ == "__main__":
    ensure_directories()
    logger.info("Starting manual task tracking test...")
    start_tracking()
    # time.sleep(5)  # Let it run for a short duration
    # stop_tracking()
