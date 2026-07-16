import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QPlainTextEdit,
                               QLineEdit, QPushButton, QHBoxLayout)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl, Signal, Slot, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from ..core.merge_engine import MergeEngine

class EditorBridge(QObject):
    # Signals for communicating with JavaScript
    setHtmlText = Signal(str)
    content_changed = Signal(str)

    @Slot(str)
    def on_content_changed(self, html):
        self.content_changed.emit(html)

class SearchBar(QWidget):
    search_requested = Signal(str, bool)
    close_requested = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f7;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
            }
            QLineEdit {
                padding: 4px;
                border: 1px solid #d1d1d6;
                border-radius: 3px;
                background-color: #ffffff;
                color: #333333;
            }
            QPushButton {
                border: 1px solid #d1d1d6;
                border-radius: 3px;
                padding: 4px 8px;
                background-color: #ffffff;
                color: #333333;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("본문에서 찾기...")
        self.search_input.textChanged.connect(self.on_text_changed)
        self.search_input.returnPressed.connect(self.find_next)
        layout.addWidget(self.search_input)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.clicked.connect(self.find_prev)
        layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("▶")
        self.btn_next.clicked.connect(self.find_next)
        layout.addWidget(self.btn_next)

        self.btn_close = QPushButton("✕")
        self.btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.btn_close)

    def on_text_changed(self, text):
        self.search_requested.emit(text, True)

    def find_next(self):
        self.search_requested.emit(self.search_input.text(), True)

    def find_prev(self):
        self.search_requested.emit(self.search_input.text(), False)

    def focus_input(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

class EditorPanelWidget(QWidget):
    html_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.current_html = ""
        self.current_values = {}
        self.pending_html = None
        self.is_loaded = False
        self.last_tab_index = 0
        self.init_ui()

        # Shortcuts for search panel
        self.shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_find.activated.connect(self.show_search_bar)

        self.shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        self.shortcut_esc.activated.connect(self.hide_search_bar)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Search Panel (Hidden by default)
        self.search_bar = SearchBar()
        self.search_bar.setVisible(False)
        self.search_bar.search_requested.connect(self.do_search)
        self.search_bar.close_requested.connect(self.hide_search_bar)
        layout.addWidget(self.search_bar)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d1d1d6;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #f2f2f7;
                border: 1px solid #d1d1d6;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 16px;
                margin-right: 2px;
                font-size: 13px;
                color: #333333;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-color: #d1d1d6;
                border-bottom: 1px solid #ffffff;
                font-weight: bold;
                color: #0078d4;
            }
            QTabBar::tab:hover {
                background: #e5e5ea;
            }
        """)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Tab 1: Edit Panel
        self.editor_view = QWebEngineView()
        # Allow local content to access local file URLs (needed for converting clipboard local files to base64)
        self.editor_view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.tabs.addTab(self.editor_view, "편집")

        # Tab 2: Preview Panel
        self.preview_view = QWebEngineView()
        self.tabs.addTab(self.preview_view, "미리보기")

        # Tab 3: HTML Source Panel
        self.source_view = QPlainTextEdit()
        self.source_view.setReadOnly(False)
        self.source_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        self.tabs.addTab(self.source_view, "HTML 원본")

        layout.addWidget(self.tabs)

        # Connect Web Channel to Edit View
        self.channel = QWebChannel()
        self.bridge = EditorBridge()
        self.bridge.content_changed.connect(self.on_bridge_content_changed)
        self.channel.registerObject("backend", self.bridge)
        self.editor_view.page().setWebChannel(self.channel)

        self.editor_view.loadFinished.connect(self.on_load_finished)

        # Load editor.html Page
        web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
        html_path = os.path.join(web_dir, "editor.html")
        self.editor_view.load(QUrl.fromLocalFile(html_path))

    def on_load_finished(self, success):
        if success:
            self.is_loaded = True
            if self.pending_html is not None:
                self.bridge.setHtmlText.emit(self.pending_html)
                self.pending_html = None

    def on_bridge_content_changed(self, html):
        self.current_html = html
        self.html_changed.emit(html)

    def set_html(self, html):
        self.current_html = html
        if self.is_loaded:
            self.bridge.setHtmlText.emit(html)
        else:
            self.pending_html = html

    def get_html(self):
        return self.current_html

    def update_preview_values(self, values):
        self.current_values = values

    def on_tab_changed(self, index):
        # 1. Sync FROM HTML Source Tab if leaving it
        if getattr(self, "last_tab_index", 0) == 2:
            new_html = self.source_view.toPlainText()
            if new_html != self.current_html:
                self.current_html = new_html
                if self.is_loaded:
                    self.bridge.setHtmlText.emit(new_html)
                else:
                    self.pending_html = new_html
                self.html_changed.emit(new_html)

        # 2. Setup the target tab
        if index == 1:  # Switch to Preview Tab
            if self.current_values:
                merged_html = MergeEngine.merge(self.current_html, self.current_values)
            else:
                merged_html = MergeEngine.highlight_unmerged(self.current_html)
            
            style_prefix = "<style>p { margin-top: 0; margin-bottom: 12px; } table { border-collapse: collapse; } th, td { border: 1px solid #d1d1d6; padding: 6px; min-width: 30px; }</style>"
            self.preview_view.setHtml(style_prefix + merged_html)
        elif index == 2:  # Switch to HTML Source Tab
            self.source_view.setPlainText(self.current_html)

        # 3. Save the new tab index as last_tab_index
        self.last_tab_index = index

    def show_search_bar(self):
        self.search_bar.setVisible(True)
        self.search_bar.focus_input()

    def hide_search_bar(self):
        self.search_bar.setVisible(False)
        self.editor_view.findText("")  # Reset match highlights
        self.editor_view.setFocus()

    def do_search(self, text, forward):
        flags = QWebEnginePage.FindFlags()
        if not forward:
            flags |= QWebEnginePage.FindBackward
        self.editor_view.findText(text, flags)
