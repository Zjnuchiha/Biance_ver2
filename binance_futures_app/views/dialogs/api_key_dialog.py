from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtWidgets import QMessageBox

class APIKeyDialog(QDialog):
    def __init__(self, username):
        super().__init__()
        self.setWindowTitle("Cấu hình Binance API")
        self.setMinimumWidth(400)
        self.username = username
        
        # Tạo UI thủ công
        layout = QFormLayout()
        
        self.api_key_input = QLineEdit()
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        
        # Thêm hướng dẫn lấy API key
        info_label = QLabel(
            "Để lấy API key từ Binance, hãy đăng nhập vào tài khoản Binance của bạn, "
            "vào phần API Management và tạo mới API key. Đảm bảo bật quyền Enable Futures."
        )
        info_label.setWordWrap(True)
        
        buttons = QHBoxLayout()
        save_button = QPushButton("Lưu")
        save_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Hủy")
        cancel_button.clicked.connect(self.reject)
        
        self.test_button = QPushButton("Kiểm tra kết nối")
        self.test_button.clicked.connect(self.on_test_connection)
        
        buttons.addWidget(save_button)
        buttons.addWidget(self.test_button)
        buttons.addWidget(cancel_button)
        
        layout.addRow(info_label)
        layout.addRow("API Key:", self.api_key_input)
        layout.addRow("API Secret:", self.api_secret_input)
        layout.addRow("", buttons)
        
        self.setLayout(layout)
    
    def show_message(self, title, message, icon=QMessageBox.Information):
        """Hiển thị thông báo"""
        QMessageBox.information(self, title, message, icon)
    
    def on_test_connection(self):
        """Gọi khi nhấn nút kiểm tra kết nối"""
        # Sự kiện này sẽ được kết nối với controller
        pass