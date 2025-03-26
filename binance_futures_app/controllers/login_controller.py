from PyQt5.QtWidgets import QApplication, QMessageBox
from views.login_view import LoginView
from views.dialogs.api_key_dialog import APIKeyDialog
from controllers.main_controller import MainController
from models.user_model import UserModel
from models import binance_data_singleton

class LoginController:
    def __init__(self):
        self.view = LoginView()
        self.model = UserModel()
        
        # Kết nối signals
        self.view.loginButton.clicked.connect(self.login)
        self.view.passwordInput.returnPressed.connect(self.login)
    
    def show(self):
        """Hiển thị cửa sổ đăng nhập"""
        self.view.show()
    
    def login(self):
        """Xử lý đăng nhập"""
        username = self.view.usernameInput.text()
        password = self.view.passwordInput.text()
        
        if not username or not password:
            QMessageBox.warning(self.view, "Lỗi", "Vui lòng nhập đầy đủ thông tin")
            return
        
        # Kiểm tra đăng nhập
        if self.model.authenticate(username, password):
            user_data = self.model.get_user(username)
            self.accept_login(username, user_data)
        else:
            QMessageBox.warning(self.view, "Lỗi", "Tên đăng nhập hoặc mật khẩu không chính xác")
    
    def accept_login(self, username, user_data):
        """Xử lý sau khi đăng nhập thành công"""
        # Kiểm tra api key nếu không phải admin
        if user_data["role"] != "admin" and (not user_data["api_key"] or not user_data["api_secret"]):
            # Hiển thị form nhập API key
            api_dialog = APIKeyDialog(username)
            
            # Tạo controller cho API key dialog
            from controllers.api_key_controller import APIKeyController
            api_controller = APIKeyController(api_dialog)
            
            if api_dialog.exec_():
                # Cập nhật API key
                api_key = api_dialog.api_key_input.text()
                api_secret = api_dialog.api_secret_input.text()
                
                self.model.update_user(username, {
                    "api_key": api_key,
                    "api_secret": api_secret
                })
                
                # Lấy thông tin user đã cập nhật
                user_data = self.model.get_user(username)
                
                # Khởi tạo BinanceDataModel singleton với API key mới
                binance_data_singleton.get_instance(api_key, api_secret)
                
                # Mở giao diện chính
                self.open_main_window(username, user_data)
        else:
            # Khởi tạo BinanceDataModel singleton trước khi mở giao diện chính
            binance_data_singleton.get_instance(user_data["api_key"], user_data["api_secret"])
            
            # Mở giao diện chính
            self.open_main_window(username, user_data)
    
    def open_main_window(self, username, user_data):
        """Mở cửa sổ chính"""
        self.main_controller = MainController(username, user_data)
        self.main_controller.show()
        self.view.close()