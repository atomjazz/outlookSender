import sys
import os
import re
import base64
import mimetypes
import urllib.parse
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                               QSplitter, QFileDialog, QMessageBox, QStatusBar)
from PySide6.QtCore import Qt, Slot, QTimer
from .template_list import TemplateListWidget
from .placeholder_panel import PlaceholderPanelWidget
from .editor_panel import EditorPanelWidget
from .send_bar import SendBarWidget
from ..core.template_manager import TemplateManager
from ..core.placeholder_manager import PlaceholderManager
from ..core.outlook_service import OutlookService
from ..core.merge_engine import MergeEngine
from ..core.logger import log_error

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("로컬 Outlook 메일 발송기")
        self.resize(1200, 800)

        # Managers
        self.template_manager = TemplateManager()
        self.placeholder_manager = PlaceholderManager(self.template_manager)

        self.current_template = None
        self.is_updating_subject = False

        self.init_ui()
        
        # Connect template manager signals
        self.template_manager.storage_path_changed.connect(self.on_storage_path_changed)
        self.template_manager.templates_changed.connect(self.scan_for_custom_placeholders)

        # Deferred progressive loading to keep start-up instant
        QTimer.singleShot(100, self.deferred_initialization)

    def deferred_initialization(self):
        # 1. Check storage folder and load templates
        self.check_storage_path()
        # 2. Check local Outlook COM connection
        self.check_outlook()
        # 3. Load Outlook account credentials
        self.send_bar.load_sender_accounts()

    def init_ui(self):
        # Menu Bar
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu("설정(&S)")
        change_dir_action = settings_menu.addAction("템플릿 저장 폴더 변경(&C)...")
        change_dir_action.triggered.connect(lambda: self.change_storage_directory(is_startup=False))



        # Main Splitter
        main_splitter = QSplitter(Qt.Horizontal)

        # Left Panel (Template List)
        self.template_list = TemplateListWidget(self.template_manager)
        self.template_list.template_selected.connect(self.on_template_selected)
        main_splitter.addWidget(self.template_list)

        # Center Panel (Editor / Preview)
        self.editor_panel = EditorPanelWidget()
        self.editor_panel.html_changed.connect(self.on_html_changed)
        main_splitter.addWidget(self.editor_panel)

        # Right Panel (Placeholders)
        self.placeholder_panel = PlaceholderPanelWidget(self.placeholder_manager)
        main_splitter.addWidget(self.placeholder_panel)

        # Set splitter sizes (20% - 60% - 20%)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 6)
        main_splitter.setStretchFactor(2, 2)

        # Bottom Panel (Send Inputs)
        self.send_bar = SendBarWidget(self.placeholder_manager)
        self.send_bar.send_triggered.connect(self.on_send_triggered)

        # Connect Send Bar Inputs to Live Preview Updates
        self.send_bar.to_input.textChanged.connect(self.update_preview_data)
        self.send_bar.cc_input.textChanged.connect(self.update_preview_data)
        self.send_bar.sender_combo.currentTextChanged.connect(self.update_preview_data)
        self.send_bar.subject_input.textChanged.connect(self.on_subject_changed)

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.addWidget(main_splitter, stretch=1)
        layout.addWidget(self.send_bar)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def check_outlook(self):
        available, error_msg = OutlookService.is_outlook_available()
        if not available:
            QMessageBox.warning(
                self, 
                "아웃룩 연동 경고", 
                f"로컬 아웃룩 앱을 연결할 수 없습니다.\n오류 내용: {error_msg}\n\n메일 발송 기능이 제한될 수 있습니다."
            )

    def check_storage_path(self):
        if not self.template_manager.storage_path:
            self.change_storage_directory(is_startup=True)
        else:
            self.template_list.load_templates()
            self.placeholder_panel.set_template_id(self.current_template["id"] if self.current_template else None)
            self.update_status_bar()

    def change_storage_directory(self, is_startup=False):
        title = "저장 폴더 설정" if is_startup else "템플릿 저장 폴더 변경"
        message = "메일 템플릿과 설정 정보를 저장할 로컬 폴더를 지정해 주세요."
        
        QMessageBox.information(self, title, message)
        
        selected_dir = QFileDialog.getExistingDirectory(
            self, 
            "저장 폴더 선택", 
            self.template_manager.storage_path or ""
        )
        
        if selected_dir:
            self.template_manager.initialize_storage_directory(selected_dir)
            self.template_list.load_templates()
            self.placeholder_panel.set_template_id(self.current_template["id"] if self.current_template else None)
            self.update_status_bar()
        else:
            if is_startup:
                QMessageBox.critical(self, "설정 필요", "저장 폴더가 설정되지 않아 프로그램을 종료합니다.")
                sys.exit(0)

    def update_status_bar(self):
        path = self.template_manager.storage_path
        self.status_bar.showMessage(f"현재 저장 경로: {path}" if path else "저장 경로가 설정되지 않았습니다.")

    def on_storage_path_changed(self, new_path):
        self.update_status_bar()

    @Slot(dict)
    def on_template_selected(self, template_data):
        try:
            self.current_template = template_data
            
            # Load content
            html_content = self.template_manager.get_template_content(template_data["file"])
            self.editor_panel.set_html(html_content)

            # Load subject
            self.is_updating_subject = True
            self.send_bar.subject_input.setText(template_data.get("default_subject", ""))
            self.is_updating_subject = False

            # Set placeholders for the selected template
            self.send_bar.set_template_id(template_data["id"])
            self.placeholder_panel.set_template_id(template_data["id"])

            # Scan and bind custom placeholders
            self.scan_for_custom_placeholders()
            self.update_preview_data()
        except Exception as ex:
            print(f"Error in on_template_selected: {ex}")
            import traceback
            traceback.print_exc()

    def on_html_changed(self, html):
        if not self.current_template:
            return
            
        # Clean MS Word VML comments and conditional blocks first
        cleaned_html = self.clean_vml_markup(html)
        vml_changed = (cleaned_html != html)
        if vml_changed:
            html = cleaned_html

        # Convert local image paths (e.g. from clipboard paste) to Base64 in Python
        converted_html, img_changed = self.convert_local_images_to_base64(html)
        if img_changed:
            html = converted_html

        if vml_changed or img_changed:
            # Temporarily disconnect to prevent infinite recursion
            self.editor_panel.html_changed.disconnect(self.on_html_changed)
            self.editor_panel.set_html(html)
            self.editor_panel.html_changed.connect(self.on_html_changed)

        # Auto-save changes
        self.template_manager.save_template_content(self.current_template["file"], html)
        
        # Scan and update
        self.scan_for_custom_placeholders()
        self.update_preview_data()

    def clean_vml_markup(self, html):
        if not html:
            return html
        # Remove VML conditional blocks
        html = re.sub(r'<!--\[if gte vml 1\].*?<!\[endif\]-->', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove VML conditional comment wrappers, keeping the standard tags inside
        html = re.sub(r'<!--\[if !vml\]-->', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<!--\[if !supportVML\]-->', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<!--\[endif\]-->', '', html, flags=re.IGNORECASE)
        return html

    def convert_local_images_to_base64(self, html):
        if not html:
            return html, False

        # Match src="file:///..." or src="C:/..." etc. in both standard img and VML v:imagedata tags
        img_pattern = re.compile(r'(<(?:img|v:imagedata)[^>]+src=["\'])(file:///[^"\']+|[a-zA-Z]:[^"\']+)(["\'][^>]*>)', re.IGNORECASE)
        changed = [False]

        def repl(match):
            prefix = match.group(1)
            src = match.group(2)
            suffix = match.group(3)

            # Decode path
            file_path = src
            if file_path.startswith("file:///"):
                file_path = file_path[8:]
            file_path = urllib.parse.unquote(file_path)
            file_path = os.path.normpath(file_path)

            if os.path.exists(file_path) and os.path.isfile(file_path):
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()
                    b64_data = base64.b64encode(data).decode('utf-8')
                    
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if not mime_type:
                        mime_type = "image/png"

                    changed[0] = True
                    return f'{prefix}data:{mime_type};base64,{b64_data}{suffix}'
                except Exception as e:
                    print(f"Error converting pasted image file {file_path} to base64: {e}")
                    return match.group(0)
            return match.group(0)

        new_html = img_pattern.sub(repl, html)
        return new_html, changed[0]

    def on_subject_changed(self, subject):
        if not self.current_template or self.is_updating_subject:
            return
            
        # Update metadata subject
        self.template_manager.update_template_meta(
            self.current_template["id"],
            self.current_template["name"],
            subject
        )
        
        # Scan and update
        self.scan_for_custom_placeholders()
        self.update_preview_data()

    def scan_for_custom_placeholders(self):
        if not self.current_template:
            return
            
        # Refresh current template data from disk
        config = self.template_manager.load_config()
        for tmpl in config.get("templates", []):
            if tmpl.get("id") == self.current_template["id"]:
                self.current_template = tmpl
                break

        html_content = self.editor_panel.get_html()
        subject_content = self.send_bar.subject_input.text()
        combined = html_content + " " + subject_content
        
        # Find all placeholders in current text
        all_keys = MergeEngine.get_unmerged_keys(combined)
        
        # Exclude standard placeholders
        placeholders = self.placeholder_manager.load_placeholders(self.current_template["id"])
        standard_keys = [ph["key"] for ph in placeholders if ph.get("target_field") != "custom"]
        
        # Built-in keys that must be excluded from custom placeholders
        builtin_keys = ["수신인", "참조인", "발송인"]
        
        # Include custom placeholders defined for this template (excluding built-ins)
        defined_custom_keys = [ph["key"] for ph in placeholders if ph.get("target_field") == "custom" and ph["key"] not in builtin_keys]
        
        # Scanned keys that are not standard/built-in
        scanned_custom_keys = [key for key in all_keys if key not in standard_keys and key not in builtin_keys]
        
        # Combine defined and scanned custom keys, preserving order and removing duplicates
        custom_keys = []
        for key in (defined_custom_keys + scanned_custom_keys):
            if key not in custom_keys:
                custom_keys.append(key)
        
        # Recreate input fields
        self.send_bar.update_custom_placeholders(custom_keys)
        
        # Bind dynamically generated fields safely
        for info in list(self.send_bar.custom_fields_inputs.values()):
            try:
                line_edit = info["input"]
                try:
                    line_edit.textChanged.disconnect(self.update_preview_data)
                except Exception:
                    pass
                line_edit.textChanged.connect(self.update_preview_data)
            except RuntimeError:
                pass
            except Exception:
                pass

    def update_preview_data(self):
        if not self.current_template:
            return
        values = self.send_bar.get_values()
        self.editor_panel.update_preview_values(values["placeholder_values"])

    @Slot(dict, bool)
    def on_send_triggered(self, values, send_now):
        try:
            if not self.current_template:
                QMessageBox.warning(self, "알림", "발송할 템플릿을 먼저 선택해 주세요.")
                return

            # 1. Validation Checks
            if not values["to"].strip():
                QMessageBox.warning(self, "입력 오류", "받는 사람 (To) 이메일 주소를 입력해 주세요.")
                return

            # Split recipients by semicolon or comma
            recipients = [r.strip() for r in values["to"].replace(",", ";").split(";") if r.strip()]
            if not recipients:
                QMessageBox.warning(self, "입력 오류", "유효한 수신자 이메일 주소를 찾을 수 없습니다.")
                return

            # 2. Check for unmerged placeholders in raw template first
            raw_html = self.editor_panel.get_html()
            raw_subject = values["subject"]
            
            # Test merge with placeholder dictionary to detect unmerged keys
            test_html = MergeEngine.merge(raw_html, values["placeholder_values"])
            test_subj = MergeEngine.merge(raw_subject, values["placeholder_values"])
            unmerged_body = MergeEngine.get_unmerged_keys(test_html)
            unmerged_subject = MergeEngine.get_unmerged_keys(test_subj)
            unmerged_all = list(set(unmerged_body + unmerged_subject))

            # Check if they are standard To/CC/From that might get overridden
            # Filter out '수신인' from warning in separate sending mode since we override it
            if values["send_mode"] == "separate" and "수신인" in unmerged_all:
                unmerged_all.remove("수신인")

            if unmerged_all:
                msg = f"치환되지 않은 항목이 본문/제목에 존재합니다:\n{', '.join(unmerged_all)}\n\n이대로 메일을 작성하시겠습니까?"
                confirm = QMessageBox.question(self, "치환 유효성 경고", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if confirm == QMessageBox.No:
                    return

            # 2.5. Verify counts for multiple keys when in separate sending mode
            if values["send_mode"] == "separate":
                mismatches = []
                multiple_keys = values.get("multiple_keys", [])
                for key in multiple_keys:
                    if key in values["placeholder_values"]:
                        raw_val = values["placeholder_values"][key]
                        val_list = [v.strip() for v in raw_val.split(',') if v.strip()]
                        if len(val_list) != len(recipients):
                            mismatches.append(f" - {key}: {len(val_list)}개")
                
                if mismatches:
                    msg = (
                        f"받는 사람 수({len(recipients)}명)와 아래 '여러 항목 입력'으로 설정된 치환 항목의 개수가 일치하지 않습니다:\n\n"
                        + "\n".join(mismatches)
                        + "\n\n이대로 계속 진행하시겠습니까?"
                    )
                    confirm_diff = QMessageBox.question(
                        self,
                        "입력 개수 불일치 경고",
                        msg,
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if confirm_diff == QMessageBox.No:
                        return

            # 3. Safety check for opening too many separate windows
            if values["send_mode"] == "separate" and not send_now and len(recipients) > 10:
                confirm_many = QMessageBox.question(
                    self,
                    "대량 창 열기 경고",
                    f"개별 발송 모드로 아웃룩 검토 창 {len(recipients)}개를 동시에 열려고 합니다.\n이 작업은 시스템 성능에 영향을 줄 수 있습니다. 계속 진행하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if confirm_many == QMessageBox.No:
                    return

            # 4. Dispatch Outlook and Send
            try:
                if values["send_mode"] == "separate":
                    # Confirm bulk send
                    if send_now:
                        confirm_bulk = QMessageBox.question(
                            self,
                            "대량 즉시 발송",
                            f"수신자 총 {len(recipients)}명에게 개별 메일을 즉시 발송하시겠습니까?\n(아웃룩 창을 거치지 않고 바로 발송됩니다.)",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if confirm_bulk == QMessageBox.No:
                            return

                    for i, recipient in enumerate(recipients):
                        # Dynamically override the '수신인' placeholder value for this recipient
                        indiv_placeholders = dict(values["placeholder_values"])
                        indiv_placeholders["수신인"] = recipient

                        # Split and bind custom placeholders if "여러 항목 입력" (multiple_keys) is checked
                        multiple_keys = values.get("multiple_keys", [])
                        for key in multiple_keys:
                            if key in indiv_placeholders:
                                raw_val = indiv_placeholders[key]
                                val_list = [v.strip() for v in raw_val.split(',') if v.strip()]
                                if val_list:
                                    if i < len(val_list):
                                        indiv_placeholders[key] = val_list[i]
                                    else:
                                        indiv_placeholders[key] = val_list[-1]

                        html_body = MergeEngine.merge(raw_html, indiv_placeholders)
                        subject = MergeEngine.merge(raw_subject, indiv_placeholders)

                        mail = OutlookService.create_mail(
                            to=recipient,
                            cc=values["cc"],
                            subject=subject,
                            html_body=html_body,
                            sender_email=values["sender_email"],
                            attachments=values.get("attachments", []),
                            save_draft=(not send_now)
                        )
                        if send_now:
                            OutlookService.send_now(mail)
                        else:
                            OutlookService.display(mail)

                    if send_now:
                        QMessageBox.information(self, "성공", f"총 {len(recipients)}개의 메일을 아웃룩 발송함으로 전송 완료하였습니다.")
                    else:
                        QMessageBox.information(self, "성공", f"총 {len(recipients)}개의 메일 검토 창을 아웃룩에 생성했습니다.")
                else:
                    # Standard Send to All (Single Email)
                    html_body = MergeEngine.merge(raw_html, values["placeholder_values"])
                    subject = MergeEngine.merge(raw_subject, values["placeholder_values"])

                    mail = OutlookService.create_mail(
                        to=values["to"],
                        cc=values["cc"],
                        subject=subject,
                        html_body=html_body,
                        sender_email=values["sender_email"],
                        attachments=values.get("attachments", []),
                        save_draft=(not send_now)
                    )

                    if send_now:
                        confirm_send = QMessageBox.question(
                            self, 
                            "메일 즉시 발송", 
                            f"받는 사람: {values['to']}\n제목: {subject}\n\n이 메일을 즉시 발송하시겠습니까?", 
                            QMessageBox.Yes | QMessageBox.No, 
                            QMessageBox.No
                        )
                        if confirm_send == QMessageBox.Yes:
                            OutlookService.send_now(mail)
                            QMessageBox.information(self, "성공", "메일을 Outlook 발송함으로 성공적으로 전송했습니다.")
                    else:
                        OutlookService.display(mail)

            except Exception as e:
                import traceback
                err_msg = traceback.format_exc()
                log_error(f"Error in on_send_triggered inner COM loop:\n{err_msg}")
                QMessageBox.critical(self, "오류", f"아웃룩 연동에 실패했습니다.\n사유: {e}\n\n자세한 정보는 error.log를 확인하십시오.")
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            log_error(f"Error in on_send_triggered outer layout:\n{err_msg}")
            QMessageBox.critical(self, "시스템 오류", f"메일을 처리하는 중 알 수 없는 시스템 오류가 발생했습니다.\n사유: {e}\n\n자세한 정보는 error.log를 확인하십시오.")
