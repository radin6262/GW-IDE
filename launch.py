import ctypes
import subprocess
import sys
import os


def restart_as_admin():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    if not is_admin:
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        sys.exit(0)




def debug_mode_available():
    """
    Checks if addons/debug.py exists safely.
    Works even if the folder doesn't exist.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    debug_path = os.path.join(base_dir, "addons", "debug.py")
    return os.path.isfile(debug_path)


def run_main_app(app_file="main.py"):
    if not os.path.exists(app_file):
        print(f"Cannot run '{app_file}', file not found.")
        return

    app_path = os.path.abspath(app_file)

    # ----------------------------
    # DEBUG MODE: run without terminal
    # ----------------------------
    if debug_mode_available():
        print("DEBUG MODE → addons/debug.py found → no terminal")

        DETACHED = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [sys.executable, app_path],
            creationflags=DETACHED
        )

    # ----------------------------
    # NORMAL MODE: run with PowerShell terminal
    # ----------------------------
    else:
        print("NORMAL MODE → no addons/debug.py → launching with terminal")

        subprocess.Popen([
            "powershell",
            "-NoExit",
            "-Command",
            f'python "{app_path}"'
        ])

    sys.exit(0)

restart_as_admin()
run_main_app()
