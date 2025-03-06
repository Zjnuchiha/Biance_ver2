from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QIcon
from PyQt5 import uic
import os
from config.config import UI_DIR, ICONS_DIR

class LoginView(QMainWindow):
    def __init__(self):
        super().__init__()
        # Nạp file UI trực tiếp
        uic.loadUi(os.path.join(UI_DIR, 'login_window.ui'), self)
        
        # Thiết lập tiêu đề và icon
        self.setWindowTitle("Đăng nhập - Binance Futures Trading")
        try:
            self.setWindowIcon(QIcon(os.path.join(ICONS_DIR, "app_icon.png")))
        except:
            pass