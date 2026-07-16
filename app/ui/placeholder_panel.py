from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QListWidgetItem, QPushButton, QInputDialog, QMessageBox, QMenu, QLabel)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag

class DraggableListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            item = self.itemAt(e.pos())
            if item:
                self.setCurrentItem(item)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # Handle custom drag setup
        item = self.currentItem()
        if not item:
            super().mouseMoveEvent(e)
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        ph_data = item.data(Qt.UserRole)
        # Pass {{key}} as the text payload
        mime_data.setText(f"{{{{{ph_data['key']}}}}}")
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction)

class PlaceholderPanelWidget(QWidget):
    def __init__(self, placeholder_manager):
        super().__init__()
        self.placeholder_manager = placeholder_manager
        self.current_template_id = None
        self.init_ui()
        self.load_placeholders()

    def set_template_id(self, template_id):
        self.current_template_id = template_id
        self.load_placeholders()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header Label
        header = QLabel("치환 문자 (본문에 드래그 삽입)")
        header.setStyleSheet("font-weight: bold; color: #555555; margin-bottom: 4px; font-size: 13px;")
        layout.addWidget(header)

        # List Widget
        self.list_widget = DraggableListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 3px 6px;
                border-radius: 4px;
                background-color: #f2f2f7;
                margin: 2px 4px;
                border: 1px solid #e5e5ea;
                font-size: 13px;
                color: #333333;
            }
            QListWidget::item:hover {
                background-color: #e5e5ea;
                border-color: #d1d1d6;
                color: #333333;
            }
            QListWidget::item:selected {
                background-color: #555555;
                color: #ffffff;
                border-color: #444444;
            }
            QListWidget::item:selected:hover {
                background-color: #444444;
                color: #ffffff;
            }
        """)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.list_widget)

        # Add Placeholder Button
        self.add_btn = QPushButton("+ 치환 문자 추가")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #0078d4;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #eff6fc;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #deecf9;
            }
            QPushButton:disabled {
                background-color: #f2f2f7;
                color: #aeaeae;
                border-color: #e5e5ea;
            }
        """)
        self.add_btn.clicked.connect(self.on_add_clicked)
        layout.addWidget(self.add_btn)

    def load_placeholders(self):
        self.list_widget.clear()
        if not self.current_template_id:
            self.add_btn.setEnabled(False)
            return
        self.add_btn.setEnabled(True)
        
        placeholders = self.placeholder_manager.load_placeholders(self.current_template_id)
        
        for ph in placeholders:
            key = ph['key']
            label = ph['label']
            target_field = ph.get('target_field', 'custom')

            if target_field != "custom":
                item_text = f"★ {label} ({{{{{key}}}}})"
            else:
                item_text = f"{{{{{key}}}}}"
                
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, ph)
            self.list_widget.addItem(item)

    def on_add_clicked(self):
        if not self.current_template_id:
            return
        name, ok = QInputDialog.getText(self, "치환 문자 추가", "새로 등록할 치환 문자 키(영어/한글)를 입력하세요:")
        if ok and name.strip():
            key = name.strip()
            # Prevent spaces or curly braces
            key = key.replace("{", "").replace("}", "").strip()
            if not key:
                return
            if self.placeholder_manager.add_placeholder(key, key, self.current_template_id, "custom"):
                self.load_placeholders()
            else:
                QMessageBox.warning(self, "오류", "이미 존재하는 치환 문자 키입니다.")

    def show_context_menu(self, pos):
        if not self.current_template_id:
            return
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        ph_data = item.data(Qt.UserRole)
        # Default placeholder fields cannot be deleted
        if ph_data.get("target_field") != "custom":
            return

        menu = QMenu(self)
        delete_action = menu.addAction("삭제")

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == delete_action:
            confirm = QMessageBox.question(self, "치환 문자 삭제", f"치환 문자 '{{{{{ph_data['key']}}}}}'를 삭제하시겠습니까?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm == QMessageBox.Yes:
                self.placeholder_manager.delete_placeholder(ph_data["key"], self.current_template_id)
                self.load_placeholders()
