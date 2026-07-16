import os
import time

def get_error_log_path():
    appdata_dir = os.path.join(os.environ.get("APPDATA", ""), "OutlookMailSender")
    settings_file = os.path.join(appdata_dir, "settings.json")
    storage_path = ""
    if os.path.exists(settings_file):
        try:
            import json
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                storage_path = data.get("storage_path", "")
        except Exception:
            pass
    if not storage_path:
        storage_path = appdata_dir
    try:
        os.makedirs(storage_path, exist_ok=True)
    except Exception:
        pass
    return os.path.join(storage_path, "error.log")

def log_error(err_text):
    try:
        log_path = get_error_log_path()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {err_text}\n")
    except Exception as e:
        print(f"Failed to write error log: {e}")
