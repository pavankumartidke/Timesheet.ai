# updater.py
import os
import sys
import json
import requests
import hashlib
import subprocess
import tempfile
import logging
import time
from pathlib import Path
import win32serviceutil
import win32service
import win32event
import win32api
import threading

class AutoUpdater:
    def __init__(self):
        self.current_version = "1.0.0"
        self.update_url = "https://your-update-server.com/updates"
        self.temp_dir = tempfile.gettempdir()
        self.app_dir = os.path.dirname(sys.executable)
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_file = os.path.join(self.temp_dir, "updater_log.txt")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def get_file_hash(self, file_path):
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def check_for_updates(self):
        """Check if updates are available"""
        try:
            response = requests.get(f"{self.update_url}/version.json")
            if response.status_code == 200:
                update_info = response.json()
                return update_info if update_info['version'] > self.current_version else None
        except Exception as e:
            logging.error(f"Error checking for updates: {str(e)}")
            return None

    def download_update(self, update_info):
        """Download the update file"""
        try:
            response = requests.get(update_info['download_url'], stream=True)
            if response.status_code == 200:
                update_file = os.path.join(self.temp_dir, "update.exe")
                with open(update_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Verify file hash
                if self.get_file_hash(update_file) == update_info['file_hash']:
                    return update_file
                else:
                    logging.error("Update file hash mismatch")
                    os.remove(update_file)
        except Exception as e:
            logging.error(f"Error downloading update: {str(e)}")
        return None

    def create_update_script(self):
        """Create a BAT script to perform the update"""
        script_path = os.path.join(self.temp_dir, "update.bat")
        current_exe = sys.executable
        
        script_content = f"""
@echo off
timeout /t 2 /nobreak > nul

:check_process
tasklist /FI "IMAGENAME eq {os.path.basename(current_exe)}" 2>NUL | find /I /N "{os.path.basename(current_exe)}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 2 /nobreak > nul
    goto check_process
)

move /y "{self.temp_dir}\\update.exe" "{current_exe}.new"
move /y "{current_exe}" "{current_exe}.old"
move /y "{current_exe}.new" "{current_exe}"

net start {os.path.basename(current_exe)}

del "%~f0"
"""
        
        with open(script_path, "w") as f:
            f.write(script_content)
        
        return script_path

    def apply_update(self, update_file):
        """Apply the update"""
        try:
            # Create and execute update script
            script_path = self.create_update_script()
            
            # Stop the service
            win32serviceutil.StopService(os.path.basename(sys.executable))
            
            # Execute update script
            subprocess.Popen(["cmd.exe", "/c", script_path], 
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           close_fds=True)
            
            return True
        except Exception as e:
            logging.error(f"Error applying update: {str(e)}")
            return False

    def run_update_check(self):
        """Main update checking routine"""
        try:
            update_info = self.check_for_updates()
            if update_info:
                logging.info(f"Update found: version {update_info['version']}")
                
                update_file = self.download_update(update_info)
                if update_file:
                    if self.apply_update(update_file):
                        logging.info("Update applied successfully")
                        return True
                    else:
                        logging.error("Failed to apply update")
            else:
                logging.info("No updates available")
        except Exception as e:
            logging.error(f"Update process failed: {str(e)}")
        
        return False

def start_update_checker():
    """Start the update checker in a separate thread"""
    updater = AutoUpdater()
    
    def check_periodically():
        while True:
            updater.run_update_check()
            # Check every 6 hours
            time.sleep(6 * 60 * 60)
    
    update_thread = threading.Thread(target=check_periodically, daemon=True)
    update_thread.start()

# Add this to your main service code
if __name__ == "__main__":
    start_update_checker()