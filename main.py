from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QTimer, QCoreApplication, QUrl
import sys
import subprocess
import os
import datetime

# ------------------------
# Detect debug mode
# ------------------------
logger = "0"
try:
    from addons.debug import *
    logger = "1"
    log("Debug module loaded! Running in DEBUG mode.")
except ModuleNotFoundError:
    print("Debug module NOT found. Running in NORMAL mode.")

def debug(val):
    if logger == "1":
        log(val)
    else:
        print(val)

# ------------------------
# Splash Screen
# ------------------------
class SplashScreen(QWidget):
    def __init__(self, main_app_script="main.py", html_file="example.html", duration_ms=4000):
        super().__init__()
        self.main_app_script = main_app_script
        self.html_file = html_file
        self.duration_ms = duration_ms

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.resize(800, 600)
        self.center_window()

        layout = QVBoxLayout(self)
        self.webview = QWebEngineView()

        html_path = os.path.abspath(self.html_file)
        debug(f"Loading splash HTML: {html_path}")
        self.webview.load(QUrl.fromLocalFile(html_path))

        layout.addWidget(self.webview)
        self.setLayout(layout)
        self.show()

        # Timer to close splash and launch main app
        self.launch_timer = QTimer(self)
        self.launch_timer.setSingleShot(True)
        self.launch_timer.timeout.connect(self.close_splash_and_start_main)
        self.launch_timer.start(self.duration_ms)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def close_splash_and_start_main(self):
        try:
            main_path = os.path.abspath(self.main_app_script)
            if not os.path.exists(main_path):
                if logger == "1":
                    log(f"ERROR: Main app not found: {main_path}")
                else:
                    print(f"ERROR: Main app not found: {main_path}")
                return

            if logger == "1":
            # Debug mode → silent launch, logs to latest.log
                pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                log(f"Launching main app silently (DEBUG mode): {main_path}")
                subprocess.Popen([pythonw, main_path])
            else:
            # Normal mode → open terminal so print works
                print(f"Launching main app in normal mode: {main_path}")
                subprocess.Popen([sys.executable, main_path])

        except Exception as e:
            if logger == "1":
                log(f"Launch error: {e}")
            else:
                print(f"Launch error: {e}")

    # Close splash
        app_instance = QCoreApplication.instance()
        if app_instance is not None:
            app_instance.quit()




# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = SplashScreen(
        main_app_script="app.py",
        html_file="splash.html",
        duration_ms=10000
    )
    sys.exit(app.exec())
