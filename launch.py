import ctypes
import subprocess
import sys
import os
def restart_as_admin():
    """
    Relaunches the current Python script with admin rights.
    If already admin, nothing happens.
    """
    # Check if already admin
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    if not is_admin:
        # Relaunch as admin
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1
        )
        sys.exit(0)  # Exit current process

restart_as_admin()
def run_main_app(app_file="main.py"):
    """
    Launches the main app in a new PowerShell window and exits the updater.
    """
    if os.path.exists(app_file):
        subprocess.Popen([
            "powershell",
            "-NoExit",  # optional: keep the PowerShell window open
            "-Command",
            f'python "{os.path.abspath(app_file)}"'
        ])
        print(f"Main app '{app_file}' launched. Exiting updater...")
        sys.exit(0)
    else:
        print(f"Cannot run '{app_file}', file not found.")

run_main_app()