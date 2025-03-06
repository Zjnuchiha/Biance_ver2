import sys
import os
import json
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from config.config import APP_NAME, SETTINGS_FILE
from controllers.login_controller import LoginController

# Thiết lập logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)

def main():
    initialize_data_files()
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
def initialize_data_files():
    """Khởi tạo các file dữ liệu nếu chưa tồn tại hoặc rỗng"""
    from config.config import USERS_FILE, TRADES_FILE, SETTINGS_FILE
    import hashlib
    import json
    import os
    
    # Tạo thư mục data nếu chưa tồn tại
    data_dir = os.path.dirname(USERS_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # Khởi tạo file users.json
    try:
        with open(USERS_FILE, "r") as f:
            users_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Tạo file mới với dữ liệu mặc định
        admin_pass = hashlib.sha256("@homonkey283".encode()).hexdigest()
        users_data = {"admin": {"password": admin_pass, "role": "admin", "api_key": "", "api_secret": ""}}
        with open(USERS_FILE, "w") as f:
            json.dump(users_data, f, indent=4)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logging.critical(f"Lỗi không xử lý được: {e}", exc_info=True)
        print(f"Đã xảy ra lỗi: {e}")