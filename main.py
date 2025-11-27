from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QTimer, QCoreApplication, QUrl
import sys
import subprocess
import os

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
        print("Loading:", html_path)

        # FIXED LINE
        self.webview.load(QUrl.fromLocalFile(html_path))

        layout.addWidget(self.webview)
        self.setLayout(layout)
        self.show()

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
            subprocess.Popen([sys.executable, self.main_app_script])
        except Exception as e:
            print("Launch error:", e)
        QCoreApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = SplashScreen(main_app_script="app.py", html_file="splash.html", duration_ms=10000)
    sys.exit(app.exec())
