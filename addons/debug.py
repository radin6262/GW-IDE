import os
from datetime import datetime

LOG_FILE = "latest.log"

def log(message: str):
    """
    Appends a debug message to latest.log with a timestamp.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Make sure log file is in same directory as script/exe
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, LOG_FILE)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
