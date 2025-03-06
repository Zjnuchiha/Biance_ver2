import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from config.config import APP_NAME, SETTINGS_FILE
from controllers.login_controller import LoginController

# Thiết lập logging sử dụng RotatingFileHandler
import logging.handlers

log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = os.path.join(log_dir, 'app.log')

# Tạo rotating file handler với kích thước tối đa là 5MB và giữ tối đa 5 file log
log_handler = logging.handlers.RotatingFileHandler(
    log_file, 
    maxBytes=5*1024*1024,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
log_handler.setFormatter(log_formatter)

# Thiết lập root logger với rotating file handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)  # Chuyển từ DEBUG sang INFO để giảm lượng log
root_logger.addHandler(log_handler)log_formatter)
root_logger.addHandler(rotating_handler)

def main():
    #initialize_data_files() #Removed
    app = QApplication(sys.argv)

    # Thiết lập thông tin ứng dụng
    app.setApplicationName(APP_NAME)
    try:
        app.setWindowIcon(QIcon("resources/icons/app_icon.png"))
    except:
        logging.warning("Không thể tải icon ứng dụng")

    # Đặt stylesheet cơ bản cho ứng dụng
    app.setStyle("Fusion")

    # Tải stylesheet từ file (nếu có)
    try:
        with open("resources/styles/styles.qss", "r") as f:
            app.setStyleSheet(f.read())
    except:
        # Tải cài đặt theme
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)

            theme = settings.get("theme", "light")

            # Áp dụng theme (đơn giản)
            if theme == "dark":
                app.setStyleSheet("""
                    QMainWindow, QDialog, QWidget { background-color: #2D2D2D; color: #EEEEEE; }
                    QLabel { color: #EEEEEE; }
                    QPushButton { background-color: #454545; color: #EEEEEE; border: 1px solid #555555; padding: 5px; border-radius: 3px; }
                    QPushButton:hover { background-color: #505050; }
                    QPushButton:pressed { background-color: #353535; }
                    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background-color: #3D3D3D; color: #EEEEEE; border: 1px solid #555555; padding: 3px; }
                    QTableWidget { background-color: #2D2D2D; color: #EEEEEE; gridline-color: #3D3D3D; }
                """)
        except:
            pass

    # Tạo cửa sổ đăng nhập
    login_controller = LoginController()
    login_controller.show()

    # Chạy ứng dụng
    return app.exec_()

def initialize_database():
    """Khởi tạo cơ sở dữ liệu SQLite."""
    from database_manager import DatabaseManager # Assumed to exist
    db_manager = DatabaseManager()
    db_manager.create_tables() # Assumed to exist in database_manager.py

if __name__ == "__main__":
    try:
        # Khởi tạo database
        initialize_database()

        # Chạy ứng dụng
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logging.critical(f"Lỗi không xử lý được: {e}", exc_info=True)
        print(f"Đã xảy ra lỗi: {e}")