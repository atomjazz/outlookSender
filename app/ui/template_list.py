from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QListWidgetItem, QPushButton, QInputDialog, QMessageBox, QMenu)
from PySide6.QtCore import Signal, Qt

class TemplateListWidget(QWidget):
    template_selected = Signal(dict)

    def __init__(self, template_manager):
        super().__init__()
        self.template_manager = template_manager
        self.templates = []
        self.init_ui()
        self.load_templates()

        # Connect updates
        self.template_manager.templates_changed.connect(self.load_templates)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # New template button
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ 새 템플릿")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.add_btn.clicked.connect(self.on_add_clicked)
        btn_layout.addWidget(self.add_btn)
        layout.addLayout(btn_layout)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 10px 8px;
                border-bottom: 1px solid #f2f2f7;
            }
            QListWidget::item:hover {
                background-color: #f2f2f7;
            }
            QListWidget::item:selected {
                background-color: #eff6fc;
                color: #0078d4;
                font-weight: 500;
            }
        """)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.list_widget)

    def load_templates(self):
        # Remember current selection ID
        selected_item = self.list_widget.currentItem()
        selected_id = None
        if selected_item:
            tmpl = selected_item.data(Qt.UserRole)
            selected_id = tmpl.get("id")

        # Temporarily block signals to avoid triggering item selection events while clearing
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        
        config = self.template_manager.load_config()
        self.templates = config.get("templates", [])
        
        selected_item_to_restore = None
        for t in self.templates:
            item = QListWidgetItem(t["name"])
            item.setData(Qt.UserRole, t)
            self.list_widget.addItem(item)
            if selected_id and t.get("id") == selected_id:
                selected_item_to_restore = item
                
        if selected_item_to_restore:
            self.list_widget.setCurrentItem(selected_item_to_restore)
        self.list_widget.blockSignals(False)

    def on_item_clicked(self, item):
        template_data = item.data(Qt.UserRole)
        self.template_selected.emit(template_data)

    def select_template_by_id(self, tmpl_id):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            tmpl = item.data(Qt.UserRole)
            if tmpl["id"] == tmpl_id:
                self.list_widget.setCurrentItem(item)
                return True
        return False

    def on_add_clicked(self):
        name, ok = QInputDialog.getText(self, "새 템플릿", "새 템플릿의 이름을 입력하세요:")
        if ok and name.strip():
            new_tmpl = self.template_manager.add_template(name.strip())
            if new_tmpl:
                self.load_templates()
                self.select_template_by_id(new_tmpl["id"])
                self.template_selected.emit(new_tmpl)

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("이름 변경...")
        duplicate_action = menu.addAction("복제")
        delete_action = menu.addAction("삭제")

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if not action:
            return

        tmpl_data = item.data(Qt.UserRole)
        tmpl_id = tmpl_data["id"]

        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "이름 변경", "새 이름을 입력하세요:", text=tmpl_data["name"])
            if ok and new_name.strip():
                self.template_manager.update_template_meta(tmpl_id, new_name.strip(), tmpl_data.get("default_subject", ""))
                self.load_templates()
                self.select_template_by_id(tmpl_id)
                
        elif action == duplicate_action:
            new_tmpl = self.template_manager.duplicate_template(tmpl_id)
            if new_tmpl:
                self.load_templates()
                self.select_template_by_id(new_tmpl["id"])
                self.template_selected.emit(new_tmpl)
                
        elif action == delete_action:
            confirm = QMessageBox.question(self, "템플릿 삭제", f"'{tmpl_data['name']}' 템플릿을 정말 삭제하시겠습니까?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm == QMessageBox.Yes:
                self.template_manager.delete_template(tmpl_id)
                self.load_templates()
