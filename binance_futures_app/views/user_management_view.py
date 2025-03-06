from PyQt5.QtWidgets import QDialog, QTableWidgetItem
from PyQt5 import uic
import os
from config.config import UI_DIR

class UserManagementView(QDialog):
    def __init__(self, username, user_data):
        super().__init__()
        self.username = username
        self.user_data = user_data
        
        # Nạp file UI trực tiếp
        uic.loadUi(os.path.join(UI_DIR, 'user_management.ui'), self)
        
        # Đặt giá trị API key hiện tại
        self.apiKeyInput.setText(user_data["api_key"])
        self.apiSecretInput.setText(user_data["api_secret"])
        
        # Nếu là admin, load danh sách người dùng và kết nối sự kiện thêm người dùng
        if user_data["role"] == "admin":
            # Giữ nguyên tab quản lý người dùng
            pass
        else:
            # Ẩn tab quản lý người dùng nếu không phải admin
            for i in range(self.tabWidget.count()):
                if self.tabWidget.tabText(i) == "Quản lý người dùng":
                    self.tabWidget.removeTab(i)
                    break
    
    def update_user_table(self, users_data):
        """Cập nhật bảng người dùng"""
        self.userTable.setRowCount(0)
        
        for i, (username, data) in enumerate(users_data.items()):
            self.userTable.insertRow(i)
            self.userTable.setItem(i, 0, QTableWidgetItem(username))
            self.userTable.setItem(i, 1, QTableWidgetItem(data["role"]))