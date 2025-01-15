# build_exe.py
from PyInstaller import main

main([
    'installer_service.py',  # Your main script
    '--onefile',            # Create single executable
    '--noconsole',          # No console window
    '--hidden-import=win32timezone',
    '--hidden-import=your_tracker',  # Your tracking module
    '--uac-admin',          # Request admin privileges
    '--name=WindowsService',  # Generic name
    '--icon=windows.ico',    # Use Windows-like icon
    '--version-file=version.txt',
    '--clean'
])