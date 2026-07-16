import sys
import os
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.core.logger import log_error

def global_excepthook(exctype, value, tb):
    import traceback
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    log_error(f"Unhandled Exception:\n{err_msg}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_excepthook

def main():
    # Fix High DPI scaling issues on Windows
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    # Establish stylesheet for global styling consistency if desired
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f7;
        }
        QWidget {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }
    """)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
