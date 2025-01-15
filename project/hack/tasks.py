import os
import time
import threading
import schedule
import pyautogui
import pandas as pd
from datetime import datetime
import win32gui
import win32process
import psutil
from openai import OpenAI
import json
import base64
from collections import defaultdict
import ctypes

#parallel agents, look and understand the threading and scheduling and how to optimize it
#total time calculation in month and each day, time calculation for each project
#how to handle the error and the retry mechanism and the backoff mechanism
#how to handle senario where the user is inactive for a long time and how to handle it, and when the screen gets locked how to handle it



# Load configuration

excel_output_path = "C:\\Projects\\Neural Networth\\Backend\\timeSheets\\TimeSheet.xlsx"
CONFIG = json.load(open("config.json"))
OPENAI_API_KEY = CONFIG["openai_api_key"]
INACTIVITY_THRESHOLD = CONFIG["inactivity_threshold"]
TRACKING_INTERVAL = CONFIG["interval_minutes"]
WINDOW_SWITCH_INTERVAL = CONFIG["window_switch_interval"]
ASSIGNED_PROJECTS = CONFIG["assigned_projects"]
Work_Item = CONFIG["work_item"]
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
   - project_name: The name or context of the project being worked on or if in any online meeting (if inferable).
   - work_items: Name the work the user was doing based on provided List.
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
    work_item: '<Work name>',
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

def convert_summaries_to_excel(json_file_path, excel_output_path):
    # Read the JSON file
    with open(json_file_path, 'r') as file:
        data = json.load(file)
    
    # Extract the list of summaries
    summaries = data.get('summaries', [])
    total_work_time_hours = data.get('total_work_time_hours', 0)
    project_times = data.get('project_times', {})


    # Add project time spent as new columns
    # Extract required keys for each summary
    filtered_summaries = []

    for project, time in project_times.items():
        filtered_summaries[project] = time

    filtered_summaries["total_work_time_hours"] = total_work_time_hours

    for summary in summaries:
        filtered_summary = {
            "software_used": summary.get("software_used", ""),
            "job_name": summary.get("job_name", ""),
            "project_name": summary.get("project_name", ""),
            "work_items": summary.get("work_items", ""),
            "description": "; ".join(summary.get("description", [])) if isinstance(summary.get("description"), list) else summary.get("description", ""),
            "time_spent": summary.get("time_spent", ""),
            "image_url": summary.get("image_url", "")
        }
        filtered_summaries.append(filtered_summary)
    
    # Convert the filtered summaries into a DataFrame
    summaries_df = pd.DataFrame(filtered_summaries)
    
    # Save to Excel
    summaries_df.to_excel(excel_output_path, index=False, engine='openpyxl')
    
    print(f"Excel file created successfully at {excel_output_path}")
def convert_summaries_to_excel(json_file_path, excel_output_path):
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
        # Add empty columns for project times to keep consistent structure
        # for project in project_times.keys():
        #     detailed_row[project] = ""
        all_rows.append(detailed_row)

    # Convert to DataFrame
    df = pd.DataFrame(all_rows)

    # Save to Excel
    df.to_excel(excel_output_path, index=False, engine='openpyxl')
    print(f"Excel file created successfully at {excel_output_path}")

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

    print(f"Daily work summary saved to: {summary_file}")

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
                        print(f"Window changed to: {current_window_title} ({current_window_info.get('process_name', 'Unknown')})")
                        
                        # Additional check for browser tabs
                        if is_browser_window(current_window_info):
                            print("Browser window detected. Taking screenshot...")
                        
                        # Capture screenshot
                        run_task()
                        
                        # Update tracking variables
                        previous_window_title = current_window_title
                        last_window_switch_time = current_time
                    except Exception as e:
                        print(f"Error in window change tracking: {e}")

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
                model="gpt-4o",
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


def summarize_text(text, timestamp, screenshot_path):
    """Summarizes the extracted text using GPT."""
    try:
        absolute_screenshot_path = os.path.abspath(screenshot_path)
        assigned_projects_str = ", ".join(f'"{project}"' for project in ASSIGNED_PROJECTS)
        project_assignment_prompt = (
            f"The user has the following assigned projects: [{assigned_projects_str}]. "
            f"The user also has the following work items available: [{Work_Item}]. "
            "Based on the screenshot content, strictly follow these rules to provide your response:\n"
            "1. Assign the task to exactly one project from the provided list of projects. "
            "   If the task does not clearly belong to any project, respond only with 'Review Needed'.\n"
            "2. Assign the task to exactly one work item from the provided list of work items. "
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
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error with GPT: {e}")
        return "Error summarizing text."


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
    
    # Append the new summary to the list
    try:
        summary_json = json.loads(summary) 
        if not summary_json.get("project_name") or summary_json["project_name"] not in ASSIGNED_PROJECTS:
            summary_json["project_name"] = "Review Needed"
        if "summaries" not in daily_data:
                    daily_data["summaries"] = [] 
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
