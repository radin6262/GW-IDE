import sys
import os
import requests
import json
import io
import zipfile
import shutil
import subprocess
from packaging.version import parse as parse_version
# PySide6 Imports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QToolBar,
    QMessageBox, QCheckBox, QComboBox, QStatusBar, QMenu, QMenuBar, QLabel,
    QFileDialog, QDialog, QPushButton, QGridLayout, QProgressBar, QSizePolicy
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QStyle
from PySide6.QtCore import (
    Qt, QTimer, Signal, QCoreApplication, QFileInfo, QDir,
    QRunnable, QThreadPool, QObject, Slot, QUrl
)
import ctypes
# --- CONFIGURATION (Moved from original updater script) ---
CURRENT_VERSION = "1.0.2.2"
PACKAGE_JSON_URL = "https://raw.githubusercontent.com/IamAbolfazlGameMaker/GW-IDE/refs/heads/main/packages.json"
SOURCE_CODE_ZIP_URL = "https://github.com/IamAbolfazlGameMaker/GW-IDE/archive/refs/heads/main.zip"
UPDATE_TEMP_DIR = "temp_update_download"
UPDATE_TARGET_DIR = os.getcwd()
# -----------------------------------------------------------

# --- Core Logic Imports (DO NOT REMOVE AT ANY Given MOMENT) ---
# NOTE: These imports are necessary for the provided structure to function.
from core.settings import load_theme, load_settings, save_settings
from core.editor import Editor 
from core.file_manager import FileManager 
from core.terminal import TerminalWidget 
from core.settings_ui import SettingsUI 
logger = "0"
try:
    from addons.debug import *
    print("Debug module loaded!")
    logger = "1"
except ModuleNotFoundError:
    print("Debug module NOT found. Defaulting to normal printing")

# -----------------------------------------------------

# --- 🛠️ UPDATE WORKER (Runs in a separate thread) ---
class UpdateWorkerSignals(QObject):
    """Signals available from background worker thread."""
    result = Signal(bool, str) # Success/Failure, Message
    version_checked = Signal(str)
    progress = Signal(str)

class UpdateWorker(QRunnable):
    """
    Runnable that performs the update check and download/install
    operations in a separate thread.
    """
    def __init__(self, action="check"):
        super().__init__()
        self.signals = UpdateWorkerSignals()
        self.action = action
        self.remote_version = None

    @Slot()
    def run(self):
        """Initial check or full update."""
        if self.action == "check":
            self._check_version()
        elif self.action == "update" and self.remote_version:
            self._perform_update(self.remote_version)

    def _get_remote_version(self):
        """Fetches the version from the remote package.json on GitHub."""
        self.signals.progress.emit("Fetching remote version information...")
        try:
            response = requests.get(PACKAGE_JSON_URL, timeout=10)
            response.raise_for_status()
            
            remote_data = response.json()
            remote_version = remote_data.get("version")
            
            if not remote_version:
                return None
                
            return remote_version
            
        except requests.exceptions.ConnectionError:
            # Explicitly catch network connection errors (like being offline)
            self.signals.result.emit(False, "NETWORK_ERROR: Could not establish a connection to the internet or GitHub.")
            return None
        except requests.exceptions.RequestException as e:
            # Handles timeouts, HTTP status errors, etc.
            self.signals.result.emit(False, f"HTTP Error fetching remote package.json: {e}")
            return None
        except json.JSONDecodeError:
            self.signals.result.emit(False, "Error: Could not decode JSON from remote package.json.")
            return None

    def _check_version(self):
        """Checks if a new version is available."""
        remote_version = self._get_remote_version()

        if remote_version is None:
            # If _get_remote_version returned None, it already emitted an error via the signal.
            return

        try:
            current = parse_version(CURRENT_VERSION)
            remote = parse_version(remote_version)
        except Exception as e:
            self.signals.result.emit(False, f"Error parsing versions: {e}. Cannot proceed with comparison.")
            return
        
        self.remote_version = remote_version # Store for potential download
        self.signals.version_checked.emit(remote_version)

        if remote > current:
            self.signals.result.emit(True, f"Update available: {remote_version} is newer than {CURRENT_VERSION}.")
        else:
            self.signals.result.emit(False, f"Local version {CURRENT_VERSION} is up-to-date.")

    def _perform_update(self, remote_version):
        """Downloads and extracts the update, now with progress reporting."""
        self.signals.progress.emit(f"Downloading source code for version {remote_version}...")
        try:
            # 1. Download the zip file (stream=True for chunking)
            zip_response = requests.get(SOURCE_CODE_ZIP_URL, stream=True, timeout=60)
            zip_response.raise_for_status()
            
            # Get total size for progress calculation (defaults to 0 if header is missing)
            total_size = int(zip_response.headers.get('content-length', 0))
            bytes_downloaded = 0
            zip_buffer = io.BytesIO()
            
            # 2. Read in chunks and update progress
            for chunk in zip_response.iter_content(chunk_size=8192):
                if chunk: # filter out keep-alive chunks
                    zip_buffer.write(chunk)
                    bytes_downloaded += len(chunk)
                    
                    # Calculate and report progress
                    if total_size > 0:
                        percent = int((bytes_downloaded / total_size) * 100)
                        # Modified progress format to include percentage clearly
                        self.signals.progress.emit(f"Downloading: {bytes_downloaded / (1024*1024):.1f} MB of {total_size / (1024*1024):.1f} MB ({percent}%)")
                    else:
                        self.signals.progress.emit(f"Downloading: {bytes_downloaded / (1024*1024):.1f} MB (Progress unknown, 0%)") # Default 0%
                        

            # Move buffer cursor to the start for ZipFile reading
            zip_buffer.seek(0)
            
            # 3. Create and clean temporary directory
            self.signals.progress.emit("Preparing file system... (100%)") # Final download step
            if os.path.exists(UPDATE_TEMP_DIR):
                shutil.rmtree(UPDATE_TEMP_DIR) 
            os.makedirs(UPDATE_TEMP_DIR, exist_ok=True)

            # 4. Extract the zip file contents using the in-memory buffer
            self.signals.progress.emit("Extracting new files... (100%)")
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                root_dir = zf.namelist()[0].split('/')[0] + '/'
                for member in zf.namelist():
                    if member.startswith(root_dir) and len(member) > len(root_dir):
                        target_path = os.path.join(UPDATE_TEMP_DIR, member[len(root_dir):])
                        
                        if member.endswith('/'):
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as outfile:
                                outfile.write(zf.read(member))
            
            # 5. Move extracted files into the target directory (crucial step for overwriting)
            self.signals.progress.emit(f"Applying update to {UPDATE_TARGET_DIR} (This will overwrite existing files)... (100%)")
            
            for item in os.listdir(UPDATE_TEMP_DIR):
                s = os.path.join(UPDATE_TEMP_DIR, item)
                d = os.path.join(UPDATE_TARGET_DIR, item)
                
                if os.path.isdir(s):
                    if os.path.exists(d):
                        # Ensure we don't accidentally remove the running script environment if possible
                        if not d.endswith('/Lib/site-packages'): # Basic safeguard
                            shutil.rmtree(d) 
                            shutil.copytree(s, d)
                    else:
                        shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d) 
            
            self.signals.progress.emit("Update applied successfully! Cleaning up temporary files. (100%)")
            shutil.rmtree(UPDATE_TEMP_DIR)
            
            # Request app restart
            self.signals.result.emit(True, "Update complete! Please restart GW IDE to finalize the changes.")

        except Exception as e:
            self.signals.progress.emit("Update failed. (0%)")
            if os.path.exists(UPDATE_TEMP_DIR):
                shutil.rmtree(UPDATE_TEMP_DIR)
            self.signals.result.emit(False, f"Update failed during file operations: {e}")

# --- 🖼️ UPDATE DIALOG (The GUI) ---

class UpdateCheckerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GW IDE Update Checker")
        self.setMinimumWidth(400)
        self.setModal(True)
        
        self.threadpool = QThreadPool()
        self.remote_version = None
        
        self._init_ui()
        self.start_check()

    def _init_ui(self):
        layout = QVBoxLayout()
        
        self.status_label = QLabel(f"Local Version: {CURRENT_VERSION}\nRemote Version: Checking...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # --- ADDED QPROGRESSBAR HERE ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        # -------------------------------
        
        self.progress_label = QLabel("Initializing update check...")
        self.progress_label.setStyleSheet("color: #777;")
        layout.addWidget(self.progress_label)
        
        self.update_button = QPushButton("Update Now")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.start_update)
        layout.addWidget(self.update_button)

        self.setLayout(layout)

    def start_check(self):
        self.progress_label.setText("Starting remote version check...")
        self.progress_bar.setValue(0)
        self.update_button.setEnabled(False)
        
        # 1. Start the check worker
        worker = UpdateWorker(action="check")
        worker.signals.result.connect(self.check_finished)
        worker.signals.version_checked.connect(self.version_info_received)
        worker.signals.progress.connect(self.update_progress_ui) # Connect to new handler
        self.threadpool.start(worker)

    def version_info_received(self, remote_version):
        self.remote_version = remote_version
        self.status_label.setText(f"Local Version: {CURRENT_VERSION}\nRemote Version: {remote_version}")

    @Slot(str)
    def update_progress_ui(self, text):
        """Updates the progress label and extracts percentage for the progress bar."""
        self.progress_label.setText(text)
        
        # Simple regex-like extraction for percentage in parentheses
        try:
            # Look for the pattern "(X%)"
            start_index = text.rfind('(')
            end_index = text.rfind('%)')
            
            if start_index != -1 and end_index != -1 and end_index > start_index:
                percent_str = text[start_index + 1 : end_index]
                percent = int(percent_str)
                self.progress_bar.setValue(percent)
            else:
                # If no clear percentage is found, default to indeterminate mode 
                # or a fixed value during non-download phases
                if "Update applied" in text or "Extracting" in text:
                     self.progress_bar.setValue(100)
                else:
                    self.progress_bar.setValue(0)
                    
        except ValueError:
            # Catch if percentage string is not an integer (e.g., "unknown")
            self.progress_bar.setValue(0)
            
    @Slot(bool, str)
    def check_finished(self, success, message):
        self.progress_label.setText(message)
        
        # Check for the specific network error message prefix
        if message.startswith("NETWORK_ERROR:"):
            self.update_button.setEnabled(False)
            self.update_button.setText("Check Failed")
            QMessageBox.critical(
                self, 
                "Connection Error", 
                "Error! You need internet to use the option for checking updates."
            )
            # Close the dialog immediately as the check cannot proceed
            self.close() 
            return

        if "Update available" in message:
            self.update_button.setEnabled(True)
            self.update_button.setText(f"Update to v{self.remote_version}")
            self.progress_bar.setValue(0) # Reset bar for the upcoming download
        elif "up-to-date" in message:
            self.update_button.setEnabled(False)
            self.update_button.setText("Up-to-Date")
            self.progress_bar.setValue(100)
        else: # General Failure/Error
            self.update_button.setEnabled(False)
            self.update_button.setText("Check Failed")
            self.progress_bar.setValue(0)
            QMessageBox.warning(self, "Update Check Failed", 
                        "The update check failed due to an unknown error. Please check the logs.")


    def start_update(self):
        if not self.remote_version:
            QMessageBox.warning(self, "Update Error", "Remote version is unknown. Cannot proceed.")
            return

        reply = QMessageBox.question(self, 'Confirm Update', 
            f"Do you want to download and install version {self.remote_version}? This will overwrite existing files.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.progress_label.setText("Starting download and install...")
            self.progress_bar.setValue(0)
            self.update_button.setEnabled(False)
            
            # 2. Start the update worker
            update_worker = UpdateWorker(action="update")
            update_worker.remote_version = self.remote_version
            update_worker.signals.result.connect(self.update_finished)
            update_worker.signals.progress.connect(self.update_progress_ui) # Connect to new handler
            self.threadpool.start(update_worker)
        
    @Slot(bool, str)
    def update_finished(self, success, message):
        self.progress_label.setText(message)
        self.progress_bar.setValue(100 if success else 0)
        
        if success:
            self.update_button.setText("Restart Required")
            QMessageBox.information(self, "Update Success", message)
            self.close()
        else:
            self.update_button.setText("Update Failed")
            QMessageBox.critical(self, "Update Failed", message)

# --- 💻 GW IDE Main Window ---

class GW(QMainWindow):

    def __init__(self):
        super().__init__()
        QCoreApplication.setApplicationName("GW IDE")

        # Use the global constant
        self.setWindowTitle(f"GW IDE - v{CURRENT_VERSION}") 
        self.setGeometry(100, 100, 1400, 900) 
        self.settings = load_settings()
        self.autosave_enabled = self.settings.get("autosave", False)
        self.current_project_name = None 
        
        self._sidebar_sizes = [280, 1120]
        self._main_splitter_sizes = [900, 50]
        
        self.init_ui()
        self.apply_theme(self.settings.get("theme", "dark"))

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(30000)
        
        self.fullscreen = False
        self.show_startup_alert()

    def show_startup_alert(self):
        QMessageBox.information(
            self,
            "WARNING!",
            "if something goes wrong, Please read the README in GitHub."
        )

    # 🎨 Status Bar Setup 
    def init_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.line_status_label = QLabel("Ln 1, Col 0") 
        
        self.lang_label = QLabel("Language: Auto")
        self.encoding_label = QLabel("Encoding: UTF-8")

        self.status_bar.addPermanentWidget(self.line_status_label) 
        self.status_bar.addPermanentWidget(self.lang_label)
        self.status_bar.addPermanentWidget(self.encoding_label)

        self.status_bar.showMessage("Ready. Welcome to GW IDE!")

    # 🎨 UI Initialization 
    def init_ui(self):
        # 1. Main widget setup
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        # 2. IDE components setup
        self.splitter_top = QSplitter(Qt.Horizontal)
        self.file_manager = FileManager()
        self.editor = Editor()

        self.splitter_top.addWidget(self.file_manager)
        self.splitter_top.addWidget(self.editor)
        self.splitter_top.setSizes([280, 1120]) 

        # Terminal setup
        self.terminal = TerminalWidget()
        self.terminal.setFixedHeight(173) 

        # 3. Add widgets to main layout
        self.main_layout.addWidget(self.splitter_top)
        self.main_layout.addWidget(self.terminal)

        # 4. Connect signals
        self.file_manager.file_open_requested.connect(self.editor.load_file)

        # 5. Settings page
        self.settings_ui = SettingsUI(self)
        self.settings_ui.hide()

        # 6. Bar Setup
        self.init_menu_bar()
        self.init_toolbar()
        self.init_status_bar()
        self.editor.currentChanged.connect(self._connect_active_editor_signals) 
        self._connect_active_editor_signals(0) # Initial connection

    # 🚨 LINE STATUS METHOD (Placeholder for implementation)
    def update_line_status(self):
        """
        Reads the cursor position from the active editor and updates the status bar.
        """
        editor = self.editor.get_current_editor()
        if editor and hasattr(editor, 'textCursor'):
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber()
            self.line_status_label.setText(f"Ln {line}, Col {col}")
        else:
            self.line_status_label.setText("Ln -, Col -")

    # 🎨 Menu Bar 
    def _connect_active_editor_signals(self, index):
        """Connects the active CodeEditorCore's signals to the GW methods."""
        editor = self.editor.get_current_editor()
        
        # Disconnect previous connections if any, to prevent multiple updates
        if hasattr(self, '_active_editor') and self._active_editor is not None:
            try:
                # Use a specific handler function if possible, or just the slot method
                self._active_editor.cursorPositionChanged.disconnect(self.update_line_status)
            except (TypeError, RuntimeError):
                pass
        
        if editor:
            self._active_editor = editor
            editor.cursorPositionChanged.connect(self.update_line_status)
            self.update_line_status() 
            
            # Update language label (basic file extension check)
            path = editor.get_file_path()
            if path and path.endswith(".py"):
                self.lang_label.setText("Language: Python")
            elif path and path.endswith(".html"):
                 self.lang_label.setText("Language: HTML")
            elif path and path.endswith(".js"):
                 self.lang_label.setText("Language: JavaScript")
            else:
                self.lang_label.setText("Language: Text")
        else:
            self._active_editor = None
            self.line_status_label.setText("Ln -, Col -")
            self.lang_label.setText("Language: Auto")

    def init_menu_bar(self):
        menu_bar = QMenuBar()
        
        file_menu = menu_bar.addMenu("&File")
        new_action = QAction("&New File", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()

        open_file_icon = self.style().standardIcon(QStyle.SP_DialogOpenButton)
        open_file_action = QAction("&Open File...", self)
        open_file_action.setShortcut("Ctrl+O")
        open_file_action.setIcon(open_file_icon)
        open_file_action.triggered.connect(self.open_file)
        file_menu.addAction(open_file_action)

        open_folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.setShortcut("Ctrl+Shift+O")
        open_folder_action.setIcon(open_folder_icon)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_icon = self.style().standardIcon(QStyle.SP_DialogSaveButton)
        save_action.setIcon(save_icon)
        save_action.triggered.connect(self.save_current)
        file_menu.addAction(save_action)
        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- View Menu ---
        view_menu = menu_bar.addMenu("&View")
        
        self.toggle_sidebar_action = QAction("Toggle &Sidebar (File Manager)", self) 
        self.toggle_sidebar_action.setShortcut("Ctrl+B") 
        self.toggle_sidebar_action.setCheckable(True)
        self.toggle_sidebar_action.setChecked(True) 
        self.toggle_sidebar_action.triggered.connect(self.toggle_file_manager_sidebar)
        view_menu.addAction(self.toggle_sidebar_action)

        view_menu.addSeparator()

        fullscreen_action = QAction("&Toggle Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # --- Tools Menu ---
        tools_menu = menu_bar.addMenu("&Tools")
        run_action_menu = QAction("&Run Code", self)
        run_action_menu.setShortcut("F5")
        run_action_menu.triggered.connect(self.run_code)
        tools_menu.addAction(run_action_menu)
        
        tools_menu.addSeparator()
        
        # Update Checker Action
        check_update_action = QAction("Check for &Updates...", self)
        check_update_icon = self.style().standardIcon(QStyle.SP_BrowserReload)
        check_update_action.setIcon(check_update_icon)
        check_update_action.triggered.connect(self.show_update_checker)
        tools_menu.addAction(check_update_action)
        
        tools_menu.addSeparator()
        
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_icon = self.style().standardIcon(QStyle.SP_FileDialogDetailedView)
        settings_action.setIcon(settings_icon)
        settings_action.triggered.connect(lambda: self.toggle_settings_view(not self.toggle_settings_action.isChecked()))
        tools_menu.addAction(settings_action)

        self.setMenuBar(menu_bar)
        
    # MODIFIED: Show Update Checker Dialog (stops and restarts autosave timer)
    def show_update_checker(self):
        """Shows the Update Checker dialog, which handles network checks internally."""
        
        # Stop autosave to prevent disk activity during update/file extraction
        self.autosave_timer.stop() 
        self.status_bar.showMessage("Autosave temporarily paused for update check.", 1000)

        dialog = UpdateCheckerDialog(self)
        dialog.exec()
        
        # Restart autosave after the dialog is closed
        self.autosave_timer.start(30000)
        self.status_bar.showMessage("Autosave restarted.", 1000)


    # 🎨 Toolbar Setup 
    def init_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # Save button
        save_icon = self.style().standardIcon(QStyle.SP_DialogSaveButton)
        save_action = QAction(save_icon, "Save (Ctrl+S)", self)
        save_action.triggered.connect(self.save_current)
        toolbar.addAction(save_action)

        # New File Action
        new_file_icon = self.style().standardIcon(QStyle.SP_FileIcon) 
        new_file_action = QAction(new_file_icon, "New File (Ctrl+N)", self)
        new_file_action.triggered.connect(self.new_file)
        toolbar.addAction(new_file_action)

        # Open File Action
        open_file_icon = self.style().standardIcon(QStyle.SP_DialogOpenButton)
        open_file_action = QAction(open_file_icon, "Open File (Ctrl+O)", self)
        open_file_action.triggered.connect(self.open_file)
        toolbar.addAction(open_file_action)

        toolbar.addSeparator()

        # Run/Execute Action 
        run_icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        run_action = QAction(run_icon, "Run Code (F5)", self)
        run_action.triggered.connect(self.run_code)
        toolbar.addAction(run_action)

        toolbar.addSeparator()
        
        # Toggle Settings button
        settings_icon = self.style().standardIcon(QStyle.SP_FileDialogDetailedView)
        self.toggle_settings_action = QAction(settings_icon, "Settings", self)
        self.toggle_settings_action.setCheckable(True)
        self.toggle_settings_action.triggered.connect(self.toggle_settings_view)
        toolbar.addAction(self.toggle_settings_action)

    # 💥 Toggle Sidebar
    def toggle_file_manager_sidebar(self):
        """Hides or shows the File Manager (the left-hand sidebar)."""
        is_visible = self.file_manager.isVisible()
        
        if is_visible:
            self.file_manager.hide()
            self._sidebar_sizes = self.splitter_top.sizes()
            # If the splitter width is zero, reset to default width for editor
            editor_width = self.splitter_top.width()
            self.splitter_top.setSizes([0, editor_width])
            self.toggle_sidebar_action.setChecked(False)
            self.status_bar.showMessage("File Manager sidebar hidden.", 3000)
        else:
            self.file_manager.show()
            
            # Restore previous sizes or a sensible default
            if hasattr(self, '_sidebar_sizes') and len(self._sidebar_sizes) == 2:
                # Ensure the restored sizes sum up to the current splitter width
                total_width = self.splitter_top.width()
                if sum(self._sidebar_sizes) != total_width:
                     # Calculate new proportional sizes if the window size changed
                    sidebar_ratio = self._sidebar_sizes[0] / sum(self._sidebar_sizes)
                    new_sidebar_width = int(total_width * sidebar_ratio)
                    self.splitter_top.setSizes([new_sidebar_width, total_width - new_sidebar_width])
                else:
                    self.splitter_top.setSizes(self._sidebar_sizes)
            else:
                # Default sizes if no previous sizes are stored
                self.splitter_top.setSizes([280, self.splitter_top.width() - 280])
                
            self.toggle_sidebar_action.setChecked(True)
            self.status_bar.showMessage("File Manager sidebar visible.", 3000)

    # CORE FUNCTION: Open Single File
    def open_file(self):
        """Opens a file dialog and loads the selected file into the editor."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;Python Files (*.py);;Text Files (*.txt)")

        if file_path:
            try:
                self.editor.load_file(file_path)
                self.status_bar.showMessage(f"Opened file: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Open Error", f"Failed to load file: {e}")
                self.status_bar.showMessage("Error: Failed to open file.", 5000)

    # CORE FUNCTION: Open Project Folder
    def open_folder(self):
        """Opens a directory dialog and sets the selected folder as the project root."""
        folder_path = QFileDialog.getExistingDirectory(self, "Open Project Folder", "")
        if folder_path:
            try:
                self.file_manager.set_root_path(folder_path)
            
                self.current_project_name = QFileInfo(folder_path).fileName()
                self.setWindowTitle(f"GW IDE - Project: {self.current_project_name}")
                self.status_bar.showMessage(f"Project folder opened: {folder_path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Folder Error", f"Failed to set project folder: {e}")
                self.status_bar.showMessage("Error: Failed to open folder.", 5000)

    def new_file(self):
        try:
            self.editor.create_new_file()
            self.status_bar.showMessage("New file created.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Core Error", f"Cannot create new file: {e}")
            self.status_bar.showMessage("Error: Cannot create new file.", 5000)

    def run_code(self):
        try:
            file_path = self.editor.get_current_file_path()

            if not file_path:
                QMessageBox.warning(self, "Run Error", "No file is currently open or saved to run.")
                self.status_bar.showMessage("Run Error: No file selected.", 5000)
                return

            self.terminal.execute_file(file_path)
            self.status_bar.showMessage(f"Executing: {file_path} in terminal...", 5000)
            
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"An unexpected error occurred during run: {e}")
            self.status_bar.showMessage("Execution failed.", 5000)

    def toggle_settings_view(self, checked):
        self.toggle_settings_action.setChecked(checked)
        
        if checked:
            self.main_layout.removeWidget(self.splitter_top)
            self.main_layout.removeWidget(self.terminal)
            self.splitter_top.hide()
            self.terminal.hide()
            self.main_layout.addWidget(self.settings_ui)
            self.settings_ui.show()
            self.status_bar.showMessage("Settings view active.")
        else:
            self.main_layout.removeWidget(self.settings_ui)
            self.settings_ui.hide()
            self.main_layout.addWidget(self.splitter_top)
            self.main_layout.addWidget(self.terminal)
            self.splitter_top.show()
            self.terminal.show()
            self.status_bar.showMessage("IDE view active. Ready.")

    def save_current(self):
        if not self.editor.save_current_file():
            QMessageBox.warning(self, "Save Error", "Could not save the file.")
            self.status_bar.showMessage("Save Error: Could not save file.", 5000)
        else:
            self.status_bar.showMessage("File saved successfully.", 3000) 

    def toggle_autosave(self, state):
        self.autosave_enabled = bool(state)
        self.settings["autosave"] = self.autosave_enabled
        save_settings(self.settings)

    def autosave(self):
        if self.autosave_enabled:
            # Check if the autosave timer is actually running before trying to save
            if self.autosave_timer.isActive():
                if self.editor.save_current_file():
                    self.status_bar.showMessage("Autosave triggered.", 1000) 
            # If the timer is not active (i.e., paused for update), do nothing.

    def apply_theme(self, theme_name):
        stylesheet = load_theme(theme_name)
        if stylesheet:
            self.setStyleSheet(stylesheet)
        else:
            self.setStyleSheet("")
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_B: 
            self.toggle_file_manager_sidebar()
        else:
            super().keyPressEvent(event)

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.showNormal()
        else:
            self.showFullScreen()
        self.fullscreen = not self.fullscreen
        self.status_bar.showMessage(f"Fullscreen: {'ON' if self.fullscreen else 'OFF'}", 3000)


if __name__ == "__main__":
    # Ensure necessary libraries are available.
    try:
        import requests
        from packaging.version import parse
    except ImportError:
        
        if logger == "1":
            log("Error: The 'requests' and 'packaging' libraries are required.")
            log("Please install them using: pip install requests packaging")
        else:
            print("Error: The 'requests' and 'packaging' libraries are required.")
            print("Please install them using: pip install requests packaging")
        sys.exit(1) # Exit if dependencies are missing

    app = QApplication(sys.argv)
    window = GW()
    window.show()
    sys.exit(app.exec())