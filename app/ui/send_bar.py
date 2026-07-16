from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLineEdit, QComboBox, QPushButton, QLabel, QGroupBox, QScrollArea, QMessageBox, QCheckBox, QFileDialog, QStyle)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QAction
import re
import os
from ..core.outlook_service import OutlookService
from ..core.logger import log_error

class EmailLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        self.import_action = QAction(self)
        self.import_action.setToolTip("텍스트 파일에서 이메일 주소 가져오기")
        self.import_action.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.import_action.triggered.connect(self.import_emails_from_file)
        self.addAction(self.import_action, QLineEdit.TrailingPosition)

    def dragEnterEvent(self, event):
        try:
            with open("drag_drop_debug.log", "a", encoding="utf-8") as f:
                f.write(f"[DragEnter] urls: {event.mimeData().hasUrls()}, formats: {event.mimeData().formats()}\n")
        except Exception:
            pass

        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        try:
            with open("drag_drop_debug.log", "a", encoding="utf-8") as f:
                f.write(f"[DragMove] urls: {event.mimeData().hasUrls()}\n")
        except Exception:
            pass

        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        try:
            with open("drag_drop_debug.log", "a", encoding="utf-8") as f:
                f.write(f"[Drop] urls: {event.mimeData().hasUrls()}, files: {[u.toLocalFile() for u in event.mimeData().urls()]}\n")
        except Exception:
            pass

        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path:
                    self.process_file(file_path)
        else:
            super().dropEvent(event)

    def import_emails_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "텍스트 파일 선택 (이메일 주소 추출)", "", "텍스트/로그 파일 (*.txt *.log *.csv *.json);;모든 파일 (*.*)"
        )
        if file_path:
            self.process_file(file_path)

    def process_file(self, file_path):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return

        try:
            content = ""
            for encoding in ['utf-8', 'cp949', 'euc-kr', 'utf-16', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content:
                # Regular expression for extracting email addresses
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                if emails:
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_emails = [x for x in emails if not (x in seen or seen.add(x))]
                    
                    current_text = self.text().strip()
                    # Parse existing email addresses
                    existing_emails = [x.strip() for x in current_text.replace(",", ";").split(";") if x.strip()]
                    
                    # Append new email addresses
                    appended_count = 0
                    for email in unique_emails:
                        if email not in existing_emails:
                            existing_emails.append(email)
                            appended_count += 1
                    
                    self.setText("; ".join(existing_emails))
                    self.setFocus()
                    
                    # Notify user of success via Status Bar if possible, otherwise QMessageBox
                    parent_window = self.window()
                    if parent_window and hasattr(parent_window, "statusBar") and parent_window.statusBar():
                        parent_window.statusBar().showMessage(f"파일에서 {appended_count}개의 새로운 이메일 주소를 추가했습니다.", 5000)
                    else:
                        QMessageBox.information(self, "성공", f"파일에서 {len(unique_emails)}개의 이메일을 찾았으며, {appended_count}개의 새로운 주소를 추가했습니다.")
                else:
                    QMessageBox.warning(self, "정보", "파일에서 이메일 주소를 찾을 수 없었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일을 읽는 중 오류가 발생했습니다.\n사유: {e}")


class SendBarWidget(QWidget):
    # Emits (values_dict, send_now_bool)
    send_triggered = Signal(dict, bool)

    def __init__(self, placeholder_manager):
        super().__init__()
        self.placeholder_manager = placeholder_manager
        self.custom_fields_inputs = {}
        self.current_template_id = None
        self.init_ui()

    def set_template_id(self, template_id):
        self.current_template_id = template_id

    def reset_checkbox(self, key):
        if key in self.custom_fields_inputs:
            checkbox = self.custom_fields_inputs[key]["check"]
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)

    def on_checkbox_changed(self, key, is_multiple):
        if not self.current_template_id:
            return
        
        # Check if send mode is "all"
        if is_multiple and self.send_mode_combo.currentData() == "all":
            QMessageBox.warning(self, "기능 사용 제한", "수신자별 구분 기능은 '개별 끊어서 보내기 (개별 발송)' 모드에서만 사용할 수 있습니다.")
            QTimer.singleShot(0, lambda: self.reset_checkbox(key))
            return

        self.placeholder_manager.set_placeholder_multiple(self.current_template_id, key, is_multiple)

    def on_send_mode_changed(self, index):
        if self.send_mode_combo.currentData() == "all":
            any_checked = False
            for key, info in list(self.custom_fields_inputs.items()):
                try:
                    if info["check"].isChecked():
                        any_checked = True
                        info["check"].blockSignals(True)
                        info["check"].setChecked(False)
                        info["check"].blockSignals(False)
                        if self.current_template_id:
                            self.placeholder_manager.set_placeholder_multiple(self.current_template_id, key, False)
                except Exception:
                    pass
            
            if any_checked:
                QMessageBox.warning(self, "기능 자동 해제", "수신자별 구분 기능은 '개별 끊어서 보내기 (개별 발송)' 모드에서만 사용할 수 있습니다.\n활성화되어 있던 수신자별 구분 항목들이 자동으로 해제되었습니다.")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Toggle Button for Mail Info
        self.toggle_btn = QPushButton("메일 기본 정보 접기 ▲")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2f2f7;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                padding: 6px;
                font-weight: bold;
                color: #555555;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_mail_group)
        main_layout.addWidget(self.toggle_btn)

        # 1. Main Send Parameters Group Box
        self.mail_group = QGroupBox("메일 기본 정보")
        self.mail_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e5e5ea;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        
        form_layout = QFormLayout(self.mail_group)
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setSpacing(8)

        # Sender Account Selection (from local Outlook profile)
        self.sender_combo = QComboBox()
        self.sender_combo.setStyleSheet("QComboBox { padding: 4px; border: 1px solid #d1d1d6; border-radius: 4px; }")
        self.sender_combo.setEditable(True)
        form_layout.addRow("보내는 사람 (From):", self.sender_combo)

        # Recipient input
        self.to_input = EmailLineEdit()
        self.to_input.setPlaceholderText("수신자 이메일 주소 (여러 개일 경우 세미콜론(;) 혹은 쉼표(,)로 구분)")
        self.to_input.setStyleSheet("QLineEdit { padding: 5px; border: 1px solid #d1d1d6; border-radius: 4px; }")
        form_layout.addRow("받는 사람 (To):", self.to_input)

        # CC Input
        self.cc_input = EmailLineEdit()
        self.cc_input.setPlaceholderText("참조자 이메일 주소 (여러 개일 경우 세미콜론(;) 혹은 쉼표(,)로 구분)")
        self.cc_input.setStyleSheet("QLineEdit { padding: 5px; border: 1px solid #d1d1d6; border-radius: 4px; }")
        form_layout.addRow("참조 (Cc):", self.cc_input)

        # Subject Input
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("메일 제목을 입력해 주세요")
        self.subject_input.setStyleSheet("QLineEdit { padding: 5px; border: 1px solid #d1d1d6; border-radius: 4px; }")
        form_layout.addRow("제목 (Subject):", self.subject_input)

        # Send Mode Combo
        self.send_mode_combo = QComboBox()
        self.send_mode_combo.setStyleSheet("QComboBox { padding: 4px; border: 1px solid #d1d1d6; border-radius: 4px; }")
        self.send_mode_combo.addItem("수신인 전체에 한 번에 보내기", "all")
        self.send_mode_combo.addItem("개별 끊어서 보내기 (개별 발송)", "separate")
        self.send_mode_combo.currentIndexChanged.connect(self.on_send_mode_changed)
        form_layout.addRow("발송 방식:", self.send_mode_combo)

        # Attachment Input
        self.attachments_list = []  # Store absolute file paths
        
        attach_widget = QWidget()
        attach_layout = QHBoxLayout(attach_widget)
        attach_layout.setContentsMargins(0, 0, 0, 0)
        attach_layout.setSpacing(4)
        
        self.attach_display = QLineEdit()
        self.attach_display.setReadOnly(True)
        self.attach_display.setPlaceholderText("첨부파일을 추가해 주세요 (여러 개 선택 가능)")
        self.attach_display.setStyleSheet("QLineEdit { padding: 5px; border: 1px solid #d1d1d6; border-radius: 4px; background-color: #f9f9fb; }")
        
        self.attach_btn = QPushButton("파일 추가...")
        self.attach_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                background-color: #f2f2f7;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)
        self.attach_btn.clicked.connect(self.on_attach_clicked)
        
        self.attach_clear_btn = QPushButton("지우기")
        self.attach_clear_btn.setStyleSheet(self.attach_btn.styleSheet())
        self.attach_clear_btn.clicked.connect(self.on_attach_clear_clicked)
        
        attach_layout.addWidget(self.attach_display)
        attach_layout.addWidget(self.attach_btn)
        attach_layout.addWidget(self.attach_clear_btn)
        
        form_layout.addRow("첨부파일:", attach_widget)

        main_layout.addWidget(self.mail_group)

        # 2. Custom Placeholders Dynamic Group Box
        self.custom_group = QGroupBox("추가 치환 항목 입력")
        self.custom_group.setStyleSheet(self.mail_group.styleSheet())
        self.custom_form = QFormLayout(self.custom_group)
        self.custom_form.setLabelAlignment(Qt.AlignRight)
        self.custom_form.setSpacing(8)
        
        # Start hidden, only shown if custom placeholders are detected
        self.custom_group.setVisible(False)
        main_layout.addWidget(self.custom_group)

        # 3. Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_display = QPushButton("Outlook에서 확인")
        self.btn_display.setStyleSheet("""
            QPushButton {
                background-color: #f2f2f7;
                color: #333333;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
                border-color: #aeaea3;
            }
        """)
        self.btn_display.clicked.connect(lambda: self.on_send_clicked(send_now=False))
        
        self.btn_send = QPushButton("바로 발송")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.btn_send.clicked.connect(lambda: self.on_send_clicked(send_now=True))

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_display)
        btn_layout.addWidget(self.btn_send)

        main_layout.addLayout(btn_layout)

    def load_sender_accounts(self):
        self.sender_combo.blockSignals(True)
        self.sender_combo.clear()
        
        # Load default sender from settings
        default_sender = self.placeholder_manager.template_manager.get_setting("default_sender", "")
        
        # Add a default option that relies on Outlook default sending account
        self.sender_combo.addItem("선택 안 함 (Outlook 기본 계정)", None)
        
        accounts = OutlookService.get_accounts()
        for acc in accounts:
            display_name = acc.get("display_name", "")
            smtp = acc.get("email", "")
            self.sender_combo.addItem(f"{display_name} ({smtp})", smtp)

        # Restore default sender if set
        if default_sender:
            # Set custom text if not found in pre-populated list
            self.sender_combo.setCurrentText(default_sender)
            
        self.sender_combo.blockSignals(False)
        self.sender_combo.editTextChanged.connect(self.on_sender_changed_text)

    def on_sender_changed_text(self, text):
        self.placeholder_manager.template_manager.save_setting("default_sender", text)

    def update_custom_placeholders(self, keys):
        """Dynamically updates text inputs for custom keys, preserving existing typed content."""
        # 1. Remove widgets for keys that are no longer present in the template
        existing_keys = list(self.custom_fields_inputs.keys())
        for key in existing_keys:
            if key not in keys:
                info = self.custom_fields_inputs[key]
                try:
                    self.custom_form.removeRow(info["layout"])
                except RuntimeError:
                    # Already deleted in C++
                    pass
                except Exception:
                    pass
                try:
                    info["input"].deleteLater()
                except Exception:
                    pass
                try:
                    info["check"].deleteLater()
                except Exception:
                    pass
                
                # Always remove from dictionary mapping
                self.custom_fields_inputs.pop(key, None)

        # 2. Add widgets for new keys that are not yet in our form
        placeholders = self.placeholder_manager.load_placeholders(self.current_template_id)
        placeholder_multi_map = {ph["key"]: ph.get("is_multiple", False) for ph in placeholders}

        for key in keys:
            if key not in self.custom_fields_inputs:
                row_layout = QVBoxLayout()
                row_layout.setSpacing(4)
                
                line_edit = QLineEdit()
                line_edit.setStyleSheet("QLineEdit { padding: 5px; border: 1px solid #d1d1d6; border-radius: 4px; }")
                
                checkbox = QCheckBox("수신자별 구분(쉼표로 구분해주세요)")
                checkbox.setStyleSheet("QCheckBox { color: #555555; font-size: 11px; margin-top: 2px; }")
                
                is_checked = placeholder_multi_map.get(key, False)
                checkbox.setChecked(is_checked)
                
                checkbox.toggled.connect(lambda checked, k=key: self.on_checkbox_changed(k, checked))
                
                row_layout.addWidget(line_edit)
                row_layout.addWidget(checkbox)
                
                self.custom_form.addRow(f"{key}:", row_layout)
                self.custom_fields_inputs[key] = {
                    "input": line_edit,
                    "check": checkbox,
                    "layout": row_layout
                }

        # 3. Toggle group visibility based on whether we have custom fields
        self.custom_group.setVisible(len(self.custom_fields_inputs) > 0)

    def get_values(self):
        custom_values = {}
        multiple_keys = []
        for key, info in list(self.custom_fields_inputs.items()):
            try:
                val = info["input"].text()
                custom_values[key] = val
                if info["check"].isChecked():
                    multiple_keys.append(key)
            except RuntimeError:
                # Handle case where the C++ widget was already deleted
                self.custom_fields_inputs.pop(key, None)
            except Exception:
                pass

        # Sender formatting - handle both editable selection and manual typing
        raw_sender = self.sender_combo.currentText().strip()
        sender_email = self.sender_combo.currentData()
        
        # Extract email inside parentheses if the user typed or edited a default item format
        import re
        email_match = re.search(r'\(([^)]+)\)', raw_sender)
        if email_match:
            sender_email = email_match.group(1).strip()
        elif not sender_email and "@" in raw_sender:
            sender_email = raw_sender

        sender_display = raw_sender.split("(")[0].strip()
        if sender_display == "선택 안 함 (Outlook 기본 계정)":
            sender_display = ""
            sender_email = ""

        # Build full placeholder lookup dictionary
        placeholder_values = {
            "수신인": self.to_input.text(),
            "참조인": self.cc_input.text(),
            "발송인": sender_display
        }
        # Merge custom ones
        placeholder_values.update(custom_values)

        return {
            "to": self.to_input.text(),
            "cc": self.cc_input.text(),
            "subject": self.subject_input.text(),
            "sender_email": sender_email,
            "send_mode": self.send_mode_combo.currentData(),
            "placeholder_values": placeholder_values,
            "multiple_keys": multiple_keys,
            "attachments": self.attachments_list
        }

    def on_attach_clicked(self):
        files, _ = QFileDialog.getOpenFileNames(self, "첨부파일 선택", "", "모든 파일 (*.*)")
        if files:
            import os
            for f in files:
                abs_path = os.path.abspath(f)
                if abs_path not in self.attachments_list:
                    self.attachments_list.append(abs_path)
            self.update_attachment_display()

    def on_attach_clear_clicked(self):
        self.attachments_list.clear()
        self.update_attachment_display()

    def update_attachment_display(self):
        import os
        if not self.attachments_list:
            self.attach_display.setText("")
            self.attach_display.setToolTip("")
        else:
            file_names = [os.path.basename(f) for f in self.attachments_list]
            self.attach_display.setText(f"선택된 파일 {len(self.attachments_list)}개: " + ", ".join(file_names))
            self.attach_display.setToolTip("\n".join(self.attachments_list))

    def on_send_clicked(self, send_now):
        try:
            values = self.get_values()
            self.send_triggered.emit(values, send_now)
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            log_error(f"Error in on_send_clicked:\n{err_msg}")
            QMessageBox.critical(self, "오류", f"발송 처리 중 오류가 발생했습니다.\n사유: {e}\n\n자세한 정보는 error.log를 확인하십시오.")

    def toggle_mail_group(self):
        is_visible = self.mail_group.isVisible()
        self.mail_group.setVisible(not is_visible)
        if is_visible:
            self.toggle_btn.setText("메일 기본 정보 펴기 ▲")
        else:
            self.toggle_btn.setText("메일 기본 정보 접기 ▼")
