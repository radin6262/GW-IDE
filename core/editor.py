# --- IMPORTS FOR core/editor.py ---
from PySide6.QtWidgets import (
    QWidget, QTabWidget, QPlainTextEdit, QScrollBar, 
    QMessageBox, QFileDialog
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QTextCharFormat, 
    QTextCursor, QSyntaxHighlighter
)
from PySide6.QtCore import (
    QSize, Qt, QRect, QFileInfo, QSignalBlocker, 
    QFile, QIODevice, Signal, QRegularExpressionMatch, QRegularExpression
)
logger = "0"
try:
    from addons.debug import *
    print("Debug module loaded!")
    logger = "1"
except ModuleNotFoundError:
    print("Debug module NOT found. Defaulting to normal printing")
# ------------------------------------------------------------------
# 🎨 SYNTAX HIGHLIGHTING: COLOR SCHEME & FORMATS
# ------------------------------------------------------------------
def Debug(val):
    if logger == "1":
        log(val)
    else:
        print(val)

# Define a color scheme (VS Code Dark+ inspired)
COLORS = {
    'background': "#1E1E1E",
    'foreground': "#D4D4D4",
    'comment': "#6A9955",
    'keyword': "#569CD6", # Blue
    'operator': "#C586C0", # Purple
    'string': "#CE9178", # Orange/Brown
    'numbers': "#B5CEA8", # Green/Yellow
    'function': "#DCDCAA", # Yellow
    'class': "#4EC9B0", # Light Blue/Teal
}

def get_format(color_key, font_weight=None):
    """Utility to create a QTextCharFormat."""
    _format = QTextCharFormat()
    _format.setForeground(QColor(COLORS[color_key]))
    if font_weight is not None:
        _format.setFontWeight(font_weight)
    return _format

# Define the actual formats
FORMATS = {
    'keyword': get_format('keyword', QFont.Bold),
    'operator': get_format('operator'),
    'string': get_format('string'),
    'comment': get_format('comment'),
    'numbers': get_format('numbers'),
    'function': get_format('function'),
    'class': get_format('class', QFont.Bold),
}

# ------------------------------------------------------------------
# 🎨 SYNTAX HIGHLIGHTING: PythonHighlighter Class
# ------------------------------------------------------------------

class PythonHighlighter(QSyntaxHighlighter):
    """A basic QSyntaxHighlighter for Python code."""
    
    # 1. Define the keyword/rule lists
    KEYWORDS = [
        'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 
        'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 
        'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 
        'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 
        'yield', 'True', 'False', 'None'
    ]
    
    OPERATORS = [
        '=', '==', '!=', '<', '<=', '>', '>=', '\\+', '-', '\\*', '/', 
        '//', '%', '\\*\\*', '\\+=', '-=', '\\*=', '/=', '%='
    ]
    
    # 2. Setup rules (order matters for complex regex)
    RULES = []

    # Rule 1: Comments (must be first)
    # The '?' makes the matching non-greedy, stopping at the first EOL
    RULES.append((QRegularExpression("#[^\n]*"), FORMATS['comment'])) 

    # Rule 2: Keywords
    # Use word boundaries (\b) to match whole words only
    for keyword in KEYWORDS:
        # \b is a word boundary; e.g. it matches 'if' but not 'elif' or 'identifierif'
        RULES.append((QRegularExpression(f"\\b{keyword}\\b"), FORMATS['keyword']))

    # Rule 3: Operators
    for operator in OPERATORS:
        RULES.append((QRegularExpression(operator), FORMATS['operator']))

    # Rule 4: Numbers (integers, floats)
    RULES.append((QRegularExpression("\\b[0-9]+(\\.[0-9]+)?\\b"), FORMATS['numbers']))

    # Rule 5: Function Definition (def identifier)
    RULES.append((QRegularExpression("\\bdef\\s+(\\w+)\\b"), FORMATS['function']))
    
    # Rule 6: Class Definition (class identifier)
    RULES.append((QRegularExpression("\\bclass\\s+(\\w+)\\b"), FORMATS['class']))

    # Rules for multi-line block (string literals - handled in highlightBlock)
    STRING_RULE = (QRegularExpression('".*?"'), FORMATS['string'])
    
    def __init__(self, parent):
        super().__init__(parent)
        self.rules = self.RULES + [self.STRING_RULE]
        self.multiline_string_format = FORMATS['string']
        # State for multi-line string: 1 = inside single quotes, 2 = inside double quotes
        # We only use state 1 for simplicity (triple-double-quotes)
        self.tri_double_quote_regex = QRegularExpression('"""')

    def highlightBlock(self, text):
        """Applies highlighting to a single block of text (line)."""
        
        # Apply standard single-line rules first
        for pattern, format in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                
                # Check for function/class capture group (Rule 5 & 6)
                if match.captured(1):
                    # Highlight the actual identifier, not the 'def ' or 'class ' part
                    self.setFormat(match.capturedStart(1), match.capturedLength(1), format)
                else:
                    self.setFormat(match.capturedStart(), match.capturedLength(), format)
        
        # Handle multi-line strings (triple quotes)
        # This is a complex logic simplified for demonstration
        
        # 1. Initial state from previous block (if any)
        self.setCurrentBlockState(0) 
        
        start_index = 0
        
        # If we were *in* a multi-line string from the previous block
        if self.previousBlockState() == 1:
            start_index = 0
            
            # Look for the closing '"""'
            match = self.tri_double_quote_regex.match(text, start_index)
            if match.hasMatch():
                # Found end: format from start_index to end
                self.setFormat(start_index, match.capturedEnd() - start_index, self.multiline_string_format)
            else:
                # Still inside: format the whole line
                self.setFormat(start_index, len(text), self.multiline_string_format)
                self.setCurrentBlockState(1) # Continue to next line
                
        # 2. Look for the start of a multi-line string
        while True:
            # Find the starting '"""'
            match_start = self.tri_double_quote_regex.match(text, start_index)
            if not match_start.hasMatch():
                break # No more multi-line strings on this line
            
            # Found a starting '"""'
            match_end = self.tri_double_quote_regex.match(text, match_start.capturedEnd())
            
            if match_end.hasMatch():
                # End is on the same line: format the whole string and continue search
                self.setFormat(match_start.capturedStart(), match_end.capturedEnd() - match_start.capturedStart(), self.multiline_string_format)
                start_index = match_end.capturedEnd()
            else:
                # End is on a later line: format from start to end of line
                self.setCurrentBlockState(1) # Set state to 'inside multi-line string'
                self.setFormat(match_start.capturedStart(), len(text) - match_start.capturedStart(), self.multiline_string_format)
                break # Stop processing this line

# ------------------------------------------------------------------
# 🚨 LINE NUMBER AREA WIDGET 
# ------------------------------------------------------------------

class LineNumberArea(QWidget):
    """Custom widget to draw line numbers."""
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        
    def sizeHint(self):
        """Tells the layout manager the required width."""
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        """Delegates the painting to the editor's core logic."""
        self.editor.lineNumberAreaPaintEvent(event)

# ------------------------------------------------------------------
# 🚨 CODE EDITOR CORE (The Text Input Widget)
# ------------------------------------------------------------------

class CodeEditorCore(QPlainTextEdit): 
    
    # Signal to notify the main window that the document's state has changed
    document_title_changed = Signal(str) 

    def __init__(self, parent=None, file_path=None):
        super().__init__(parent)
        
        # Internal state
        self._file_path = file_path
        self._is_dirty = False
        self._title = "Untitled" if file_path is None else QFileInfo(file_path).fileName()

        # Appearance setup (basic example)
        font = QFont("Monospace", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))

        # --- 🎨 SYNTAX HIGHLIGHTING: Integration START ---
        self.setStyleSheet(f"QPlainTextEdit {{ background-color: {COLORS['background']}; color: {COLORS['foreground']}; border: 1px solid #1E1E1E; }}")
        # Instantiate and set the highlighter
        self.highlighter = PythonHighlighter(self.document())
        # --- 🎨 SYNTAX HIGHLIGHTING: Integration END ---

        # 🚨 LINE NUMBER IMPLEMENTATION START
        self.lineNumberArea = LineNumberArea(self)
        
        # Connect necessary signals
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        # Connect vertical scroll bar value changes
        self.verticalScrollBar().valueChanged.connect(lambda: self.updateLineNumberArea(self.rect(), 0))
        
        # Initial call to set the margin
        self.updateLineNumberAreaWidth(0)
        # 🚨 LINE NUMBER IMPLEMENTATION END
        
        # Document modification tracking
        self.document().modificationChanged.connect(self._update_dirty_state)
        self.document().setModified(False)

        # Initial title update
        self.document_title_changed.emit(self.get_tab_title())
        
    def get_tab_title(self):
        """Returns the title string for the QTabWidget."""
        star = " *" if self._is_dirty else ""
        return self._title + star

    def get_file_path(self):
        return self._file_path

    # Added required method for Save As fallback in CFL main window (new feature)
    def get_default_filename(self):
        """Provides a default name for Save As dialog if file is untitled."""
        # Ensure 'untitled' default gets a .txt extension
        if "untitled" in self._title.lower() and not self._title.endswith(('.txt', '.py')):
            return self._title + ".txt"
        return self._title

    def _update_dirty_state(self, modified):
        """Updates the dirty state and notifies the main window."""
        self._is_dirty = modified
        self.document_title_changed.emit(self.get_tab_title())
    def set_file_path(self, path):
        if getattr(self, "_file_path", None) == path:
            return  # already set, don't do anything
        self._file_path = path
    # any other logic like updating UI


    # -------------------------------------------------------------
    # 🚨 CORE LINE NUMBER LOGIC METHODS 
    # -------------------------------------------------------------

    def lineNumberAreaWidth(self):
        """Calculates the optimal width based on the number of lines."""
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value /= 10
            digits += 1
            
        # space = 3px padding + font width * digits + 8px right margin
        space = 3 + self.fontMetrics().horizontalAdvance('0') * digits + 8
        return space

    def updateLineNumberAreaWidth(self, _):
        """Sets the margin of the viewport to reserve space for the line numbers."""
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
        
    def resizeEvent(self, event):
        """Overrides resize event to reposition the line number widget."""
        super().resizeEvent(event) 
        
        cr = self.contentsRect()
        # Set the geometry of the LineNumberArea to be on the left margin
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        """
        The method that actually draws the numbers, called by the LineNumberArea's paintEvent.
        """
        painter = QPainter(self.lineNumberArea)
        
        # --- 🎨 Styling ---
        # Changed to match the dark theme background
        painter.fillRect(event.rect(), QColor(COLORS['background'])) 
        painter.setPen(QColor("#5c6370")) # Text color for numbers
        painter.setFont(self.font())
        # --- 🎨 Styling End ---

        # Calculate the visible area
        block = self.firstVisibleBlock()
        block_number = block.blockNumber() 
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # Loop through all visible blocks (lines)
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_number = str(block_number + 1) # 1-indexed line number
                
                painter.drawText(
                    0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(),
                    Qt.AlignRight, line_number
                )
                
            block = block.next()
            if not block.isValid():
                break
                
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
            
    def updateLineNumberArea(self, rect, dy):
        """
        Updates or scrolls the line number area when text is edited or scrolled.
        """
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    # -------------------------------------------------------------
    # --- File I/O and Save Logic (REQUIRED FOR MAIN WINDOW)
    # -------------------------------------------------------------

    def save_file(self, path=None):
        """Saves the document content to the specified path or current path."""
        path = path if path else self._file_path
        if not path:
            Debug("DEBUG: save_file called with no path, returning False.")
            return False

        file = QFile(path)
        if not file.open(QIODevice.WriteOnly | QIODevice.Text):
            Debug(f"DEBUG: Failed to open file for writing: {path}. Error: {file.errorString()}")
            QMessageBox.warning(self, "Save Error", f"Cannot write file {path}:\n{file.errorString()}")
            return False
        
        try:
            # We must use encode('utf-8') for reliable file writing
            file.write(self.toPlainText().encode('utf-8'))
            file.close()
            
            # Update state only upon successful save
            self._file_path = path
            self._title = QFileInfo(path).fileName()
            self.document().setModified(False) 
            self.document_title_changed.emit(self.get_tab_title()) # Notify tab widget title change
            Debug(f"DEBUG: Successfully saved file to: {path}")
            return True
        except Exception as e:
            Debug(f"DEBUG: Unexpected error during file write: {e}")
            QMessageBox.critical(self, "Write Error", f"An unexpected error occurred during save: {e}")
            return False

    def load_file_content(self, path):
        """Loads text content from a file."""
        file = QFile(path)
        if not file.open(QIODevice.ReadOnly | QIODevice.Text):
            QMessageBox.warning(self, "Open Error", f"Cannot read file {path}:\n{file.errorString()}")
            return False
        
        try:
            content = str(file.readAll(), 'utf-8')
            file.close()

            # Block signals while loading to prevent spurious dirty state
            with QSignalBlocker(self.document()):
                self.setPlainText(content)
            
            self._file_path = path
            self._title = QFileInfo(path).fileName()
            self.document().setModified(False)
            self.document_title_changed.emit(self.get_tab_title())
            
            # Re-highlight the document after loading new content
            self.highlighter.rehighlight()
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "Read Error", f"An unexpected error occurred during load: {e}")
            return False

# ------------------------------------------------------------------
# 🚨 EDITOR (QTabWidget wrapper, REQUIRED FOR MAIN WINDOW)
# ------------------------------------------------------------------
# (The Editor class remains unchanged as the core logic is in CodeEditorCore)

class Editor(QTabWidget):
    document_title_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self.currentChanged.connect(self._handle_tab_change)
        
        # Create an initial empty file
        self.create_new_file()

    def get_current_editor(self):
        """Returns the current CodeEditorCore instance or None."""
        return self.currentWidget()

    def get_current_file_path(self):
        """Returns the file path of the current editor."""
        editor = self.get_current_editor()
        return editor.get_file_path() if editor else None

    def create_new_file(self):
        """Adds a new, unsaved tab."""
        new_editor = CodeEditorCore(self)
        
        # Connect the new editor's title change signal to the QTabWidget's signal
        new_editor.document_title_changed.connect(self._update_tab_title)
        
        index = self.addTab(new_editor, new_editor.get_tab_title())
        self.setCurrentIndex(index)
        
        # Manually ensure the main window title is updated for the new tab
        self.document_title_changed.emit(new_editor.get_tab_title())


    def load_file(self, path):
        """Checks if file is open, otherwise opens it."""
        # Check if file is already open
        for i in range(self.count()):
            editor = self.widget(i)
            if editor.get_file_path() == path:
                self.setCurrentIndex(i)
                return

        new_editor = CodeEditorCore(self)
        if new_editor.load_file_content(path):
            new_editor.document_title_changed.connect(self._update_tab_title)
            index = self.addTab(new_editor, new_editor.get_tab_title())
            self.setCurrentIndex(index)
        else:
            # Cleanup the failed editor instance
            del new_editor
        
    def save_current_file(self):
        """Saves the current file, prompting for path if unsaved."""
        editor = self.get_current_editor()
        if not editor:
            Debug("DEBUG: save_current_file called but no editor widget is active.")
            return False
            
        # Only skip saving if the document is NOT modified AND already has a path.
        if not editor.document().isModified() and editor.get_file_path() is not None:
            Debug("DEBUG: Document not modified and already saved, skipping.")
            return True

        if editor.get_file_path() is None:
            # If path is unknown, prompt for a path (Save As)
            default_name = editor.get_default_filename() or "untitled.txt"
            
            # 💡 FIX: Reordering filter to default to Text Files (*.txt)
            filter_str = "Text Files (*.txt);;All Files (*);;Python Files (*.py)"

            file_path, _ = QFileDialog.getSaveFileName(self, "Save File", default_name, filter_str)
            
            if file_path:
                Debug(f"DEBUG: QFileDialog returned path: {file_path}")
                return editor.save_file(file_path)
            else:
                Debug("DEBUG: QFileDialog cancelled.")
                return False # User cancelled save
        else:
            # Existing file, perform direct save
            Debug(f"DEBUG: Saving existing file to: {editor.get_file_path()}")
            return editor.save_file()

    def _update_tab_title(self, title):
        """Updates the tab title and forwards the signal to the main window."""
        editor = self.sender()
        index = self.indexOf(editor)
        if index != -1:
            self.setTabText(index, title)
            
        # If this is the active tab, update the main window title
        if self.currentIndex() == index:
            self.document_title_changed.emit(title)
        
    def _handle_tab_change(self, index):
        """Handles when the active tab changes."""
        editor = self.widget(index)
        if editor:
            self.document_title_changed.emit(editor.get_tab_title())

    def _close_tab(self, index):
        """Handles closing a tab, checking for unsaved changes."""
        editor = self.widget(index)
        if editor.document().isModified():
            # Prompt user to save changes
            ret = QMessageBox.warning(self, "Unsaved Changes",
                f"Document '{editor.get_tab_title().rstrip(' *')}' has been modified.\nDo you want to save your changes?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

            if ret == QMessageBox.Save:
                if not self.save_current_file():
                    return # Cancelled save, don't close
            elif ret == QMessageBox.Cancel:
                return # Cancelled close

        # Safe to close
        self.removeTab(index)
        editor.deleteLater() 
        
        # If all tabs are closed, create a new one
        if self.count() == 0:
            self.create_new_file()