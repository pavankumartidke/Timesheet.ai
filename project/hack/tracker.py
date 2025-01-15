import os
import time
import threading
import schedule
import pyautogui
from datetime import datetime
import win32gui
import win32process
import psutil
from openai import OpenAI
import json
import base64
from collections import defaultdict
import ctypes
from threading import Lock

#parallel agents, look and understand the threading and scheduling and how to optimize it

# Load configuration
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
GPT_MODEL = "gpt-4"
SYSTEM_PROMPT = """
You are a productivity assistant. Your task is to:
1. Analyze the provided JSON input and extract actionable tasks and activities.
2. Organize the information into a structured JSON format suitable for maintaining a timesheet.
3. Don't return any other text than the JSON.
4. Ensure the JSON includes the following fields:
   - software_used: The software, application, or window identified.
   - job_name: The name of the job being worked on like designing, coding, emailing, searching, etc.
   - project_name: The name or context of the project being worked on (if inferable).
   - work_items: A concise description of the task being performed.
   - description: A list of items, actions, or subtasks related to the task.
   - time: current time of the current session.
   - image_url: The URL of the image associated with this analysis.

If no specific software, project, or tasks are found, provide a general summary of the image content in the 'task' field and include 'N/A' for fields where no data is available.

Output the response as a JSON object following this structure:
example:
{
    software_used: '<software name>',
    job_name: '<job name>',
    project_name: '<project name>',
    work_items: '<concise description>',
    description: ['<item 1>', '<item 2>', ...],
    time_spent: '<time>',
    image_url: '<image URL>'
}
Constraints: Ensure the output is raw JSON only. Avoid any extraneous text or explanations. Be concise return only the JSON and focus on accuracy.
"""

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


def is_system_locked():
    """Check if the system is locked."""
    user32 = ctypes.windll.User32
    return user32.GetForegroundWindow() == 0

def determine_project():
    # Check the assigned projects in the last recorded summary file
    latest_summary = get_latest_summary()

    # If a project is already identified, we use it
    if latest_summary:
        current_project = latest_summary.get("project_name", "Review Needed")
    else:
        current_project = "Review Needed"

    return current_project

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

            if is_system_locked():
                # System is locked, save summary if needed
                print("System is locked. Triggering daily work summary save.")
                save_daily_work_summary()
                continue

            # Check for inactivity
            last_input = pyautogui.getActiveWindow()  # Get active window as an indicator of activity
            if last_input is None:
                if inactivity_start_time is None:
                    inactivity_start_time = time.time()  # Mark the start of inactivity
                elif time.time() - inactivity_start_time >= INACTIVITY_THRESHOLD:
                    # Inactivity threshold exceeded
                    print("Inactivity threshold exceeded. Triggering daily work summary save.")
                    save_daily_work_summary()
                    continue
            else:
                # Reset inactivity tracker on activity
                inactivity_start_time = None

            # Update total work time
            if work_start_time is None:
                work_start_time = time.time()
            total_work_seconds += 1

            # Simulate per-project tracking (replace logic as per your needs)
            
            project_name = determine_project()
            if project_name not in current_project_times:
                current_project_times[project_name] = 0
            current_project_times[project_name] += 1
        
    finally:
        # Ensure data is saved when tracking stops
        print("Tracking stopped. Saving final summary.")
        save_daily_work_summary()

def save_daily_work_summary():
    """Save the daily work summary with total work time and project details."""
    global total_work_seconds, current_project_times, work_start_time

    if total_work_seconds == 0:
        print("No work logged. Skipping save.")
        return

    # Prepare the current day's summary data
    date_str = datetime.now().strftime("%Y-%m-%d")
    new_summary = {
        "total_work_time_hours": round(total_work_seconds / 3600, 2),
        "project_times": {
            project: round(seconds / 3600, 2) for project, seconds in current_project_times.items()
        }
    }

    # Define the file path
    file_date_str = datetime.now().strftime("%Y%m%d")
    summary_file = os.path.join(TIMESHEETS_DIR, f"summary_{file_date_str}.json")

    # File operation within a lock for thread safety
    with file_lock:
        if not os.path.exists(summary_file):
            # Initialize the structure if the file doesn't exist
            existing_data = {"date": date_str, "summaries": []}
        else:
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # Ensure "summaries" key exists
                if "summaries" not in existing_data:
                    existing_data["summaries"] = []
            except (json.JSONDecodeError, FileNotFoundError):
                # Handle corrupted or empty files
                print("Error loading existing file, initializing new structure.")
                existing_data = {"date": date_str, "summaries": []}

        # Check if today's summary already exists
        existing_summary = None
        for summary in existing_data["summaries"]:
            if summary["date"] == date_str:
                existing_summary = summary
                break

        if existing_summary:
            # Merge new data into the existing summary
            existing_summary["total_work_time_hours"] += new_summary["total_work_time_hours"]

            for project, time in new_summary["project_times"].items():
                if project in existing_summary["project_times"]:
                    existing_summary["project_times"][project] += time
                else:
                    existing_summary["project_times"][project] = time
        else:
            # Add the new summary if no existing one for today
            existing_data["summaries"].append(new_summary)

        # Save the updated data back to the file
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4)

    print(f"Daily work summary saved to: {summary_file}")

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
        executable_path = process.exe()
        return {
            'hwnd': hwnd,
            'window_title': window_title,
            'process_name': process_name,
            'executable_path': executable_path
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
    
    current_window_info = get_active_window_info()
    
    if current_window_info:
        current_window_title = current_window_info['window_title']
        
        # Check if window has changed
        if current_window_title != previous_window_title:
            current_time = time.time()
            
            # Debounce mechanism: wait few seconds between screenshots
            with window_switch_lock:
                if current_time - last_window_switch_time >= WINDOW_SWITCH_INTERVAL:
                    print(f"Window changed to: {current_window_title} ({current_window_info['process_name']})")
                    
                    # Additional check for browser tabs
                    if is_browser_window(current_window_info):
                        print("Browser window detected. Taking screenshot...")
                    
                    # Capture screenshot
                    run_task()
                    
                    # Update tracking variables
                    previous_window_title = current_window_title
                    last_window_switch_time = current_time

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
                model="gpt-4-vision-preview",
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
        text_response = response.choices[0].message.content
        return text_response
    except Exception as e:
        print(f"Error with Vision model: {e}")
        return "Error extracting text."


def log_extracted_text(text, timestamp):
    """Logs the extracted text to the logs folder."""
    log_file = os.path.join(LOGS_DIR, f"log_{timestamp}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(text)
    return log_file

def some_function():

    return "This is healthy"

def summarize_text(text, timestamp, screenshot_path):
    """Summarizes the extracted text using GPT."""
    try:
        absolute_screenshot_path = os.path.abspath(screenshot_path)
        assigned_projects_str = ", ".join(f'"{project}"' for project in ASSIGNED_PROJECTS)
        project_assignment_prompt = (
            f"The user has the following assigned projects: [{assigned_projects_str}]. "
            "Based on the screenshot content, decide which project this task belongs to. "
            "If it doesn't belong to any project, return 'Review Needed'."
        )
        combined_prompt = SYSTEM_PROMPT + "\n\n" + project_assignment_prompt
        
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": combined_prompt},
                {"role": "user", "content": f"Analyze the following JSON and summarize it for a timesheet: \n\n{text}. For the image_url field, provide the screenshot path: {absolute_screenshot_path} and for the timestamp field, provide the timestamp: {timestamp}"}
            ],
            max_tokens=1000,
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error with GPT: {e}")
        return "Error summarizing text."


def save_summary(summary, timestamp):
    """Saves the summary to the timesheets folder."""
    date_str = timestamp.split("_")[0]  # Format: YYYYMMDD
    daily_summary_file = os.path.join(TIMESHEETS_DIR, f"summary_{date_str}.json")

    if os.path.exists(daily_summary_file):
        with open(daily_summary_file, "r", encoding="utf-8") as f:
            daily_data = json.load(f)
    else:
        daily_data = {"date": date_str, "summaries": []}
    
    # Append the new summary to the list
    try:
        summary_json = json.loads(summary) 
        if not summary_json.get("project_name") or summary_json["project_name"] not in ASSIGNED_PROJECTS:
            summary_json["project_name"] = "Review Needed"
        daily_data["summaries"].append(summary_json)
    except json.JSONDecodeError as e:
        print(f"Failed to decode summary JSON: {e}")
        return None
    
    with open(daily_summary_file, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, indent=4)

    print(f"Summary saved to: {daily_summary_file}")
    return daily_summary_file



def run_task():
    """Handles the main task: capture screenshot, extract text, and summarize."""
    # Capture a screenshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = capture_screen(timestamp)
    print(f"Screenshot saved: {screenshot_path}")

    # Extract text from the screenshot
    extracted_text = extract_text_from_image(screenshot_path)
    log_file = log_extracted_text(extracted_text, timestamp)
    print(f"Extracted text logged: {log_file}")

    # Summarize the extracted text
    summary = summarize_text(extracted_text, timestamp, screenshot_path)
    summary_file = save_summary(summary, timestamp)
    print(f"Summary saved: {summary_file}")

def window_change_monitor():
    """Continuously monitor window changes in a separate thread."""
    global tracking_active
    while tracking_active:
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
        work_tracker_thread = threading.Thread(target=track_work_time, daemon=True)
        work_tracker_thread.start()
         # Start window change monitoring thread
        window_monitor_thread = threading.Thread(target=window_change_monitor, daemon=True)
        window_monitor_thread.start()

        schedule.every(TRACKING_INTERVAL).minutes.do(run_task)
        threading.Thread(target=scheduler_loop, daemon=True).start()
        print("Tracking started.")


def stop_tracking():
    """Stops the tracking process."""
    global tracking_active
    if tracking_active:
        tracking_active = False
        schedule.clear()
        print("Tracking stopped.")


# Testing endpoints if needed
if __name__ == "__main__":
    print("Starting manual task tracking test...")
    start_tracking()
    time.sleep(10)  # Let it run for a short duration
    stop_tracking()
