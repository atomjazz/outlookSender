import os
import json
import shutil
import time
from PySide6.QtCore import QObject, Signal

class TemplateManager(QObject):
    # Signals for notifying UI updates
    templates_changed = Signal()
    storage_path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.appdata_dir = os.path.join(os.environ.get("APPDATA", ""), "OutlookMailSender")
        os.makedirs(self.appdata_dir, exist_ok=True)
        self.settings_file = os.path.join(self.appdata_dir, "settings.json")
        
        # Load user-specified path from Settings
        self.storage_path = self.get_setting("storage_path", "")

    def get_setting(self, key, default=""):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get(key, default)
            except Exception as e:
                print(f"Error reading settings.json: {e}")
        return default

    def save_setting(self, key, value):
        data = {}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[key] = value
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving setting {key} in settings.json: {e}")

    def save_storage_path_to_settings(self, path):
        self.storage_path = path
        self.save_setting("storage_path", path)
        self.storage_path_changed.emit(path)

    def initialize_storage_directory(self, target_path):
        """Initializes target_path with default config and templates if they do not exist."""
        os.makedirs(target_path, exist_ok=True)
        templates_dir = os.path.join(target_path, "templates")
        os.makedirs(templates_dir, exist_ok=True)

        config_path = os.path.join(target_path, "config.json")
        
        # Determine source path of default storage
        default_app_storage = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "storage"
        )

        # Copy default config.json if not present
        if not os.path.exists(config_path):
            default_config = os.path.join(default_app_storage, "config.json")
            if os.path.exists(default_config):
                shutil.copy(default_config, config_path)
            else:
                # Minimal fallback config
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump({"placeholders": [], "templates": []}, f, ensure_ascii=False, indent=2)

        # Copy default templates if not present
        default_templates_dir = os.path.join(default_app_storage, "templates")
        if os.path.exists(default_templates_dir):
            for filename in os.listdir(default_templates_dir):
                dest_file = os.path.join(templates_dir, filename)
                if not os.path.exists(dest_file):
                    shutil.copy(os.path.join(default_templates_dir, filename), dest_file)

        self.save_storage_path_to_settings(target_path)
        self.templates_changed.emit()

    def get_config_path(self):
        if not self.storage_path:
            return ""
        return os.path.join(self.storage_path, "config.json")

    def load_config(self):
        path = self.get_config_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                # Migration: if global placeholders exist, copy them to templates that don't have local placeholders
                global_placeholders = config.get("placeholders", [])
                if global_placeholders:
                    changed = False
                    for tmpl in config.get("templates", []):
                        if "placeholders" not in tmpl:
                            tmpl["placeholders"] = list(global_placeholders)
                            changed = True
                    if changed:
                        try:
                            with open(path, "w", encoding="utf-8") as f:
                                json.dump(config, f, ensure_ascii=False, indent=2)
                        except Exception as e:
                            print(f"Error saving migrated config: {e}")
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
        return {"placeholders": [], "templates": []}

    def save_config(self, config_data):
        path = self.get_config_path()
        if not path:
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            self.templates_changed.emit()
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get_template_content(self, filename):
        if not self.storage_path or not filename:
            return ""
        filepath = os.path.join(self.storage_path, "templates", filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading template file {filename}: {e}")
        return ""

    def save_template_content(self, filename, content):
        if not self.storage_path or not filename:
            return False
        filepath = os.path.join(self.storage_path, "templates", filename)
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving template file {filename}: {e}")
            return False

    def add_template(self, name, subject=""):
        config = self.load_config()
        timestamp = int(time.time() * 1000)
        tmpl_id = f"tmpl_{timestamp}"
        filename = f"{tmpl_id}.html"

        # Save an empty HTML file
        initial_html = "<p>새로운 템플릿입니다. 내용을 편집해 주세요.</p>"
        if not self.save_template_content(filename, initial_html):
            return None

        # Add to config
        new_template = {
            "id": tmpl_id,
            "name": name,
            "file": filename,
            "created_at": iso_now(),
            "updated_at": iso_now(),
            "default_subject": subject,
            "placeholders": []
        }
        config.setdefault("templates", []).append(new_template)
        
        if self.save_config(config):
            return new_template
        return None

    def delete_template(self, tmpl_id):
        config = self.load_config()
        templates = config.get("templates", [])
        
        target_template = None
        for t in templates:
            if t["id"] == tmpl_id:
                target_template = t
                break
                
        if not target_template:
            return False

        # Delete HTML file
        filename = target_template.get("file")
        if filename:
            filepath = os.path.join(self.storage_path, "templates", filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Error removing file {filepath}: {e}")

        # Remove from config
        templates.remove(target_template)
        config["templates"] = templates
        return self.save_config(config)

    def update_template_meta(self, tmpl_id, name, subject):
        config = self.load_config()
        for t in config.get("templates", []):
            if t["id"] == tmpl_id:
                t["name"] = name
                t["default_subject"] = subject
                t["updated_at"] = iso_now()
                break
        return self.save_config(config)

    def duplicate_template(self, tmpl_id):
        config = self.load_config()
        original = None
        for t in config.get("templates", []):
            if t["id"] == tmpl_id:
                original = t
                break
        if not original:
            return None

        # Load content
        content = self.get_template_content(original["file"])
        
        # Generate new item
        timestamp = int(time.time() * 1000)
        new_id = f"tmpl_{timestamp}"
        new_filename = f"{new_id}.html"
        
        # Save content to new file
        if not self.save_template_content(new_filename, content):
            return None

        new_template = {
            "id": new_id,
            "name": f"{original['name']} - 복사본",
            "file": new_filename,
            "created_at": iso_now(),
            "updated_at": iso_now(),
            "default_subject": original.get("default_subject", ""),
            "placeholders": list(original.get("placeholders", []))
        }
        config.setdefault("templates", []).append(new_template)
        
        if self.save_config(config):
            return new_template
        return None

def iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
