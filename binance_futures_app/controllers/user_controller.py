from views.user_management_view import UserManagementView
from models.user_model import UserModel
from models.trade_model import TradeModel
from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QComboBox, QHBoxLayout, QPushButton, QMessageBox


class UserController:
    def __init__(self, username, user_data):
        self.username = username
        self.user_data = user_data
        self.model = UserModel()
        self.trade_model = TradeModel()
        self.view = UserManagementView(username, user_data)
        
        # Kết nối signals
        self.connect_signals()
        
        # Load dữ liệu
        if user_data["role"] == "admin":
            self.load_users()
    
    def connect_signals(self):
        """Kết nối các signals"""
        self.view.changePasswordButton.clicked.connect(self.change_password)
        self.view.updateApiButton.clicked.connect(self.update_api)
        
        if self.user_data["role"] == "admin":
            self.view.addUserButton.clicked.connect(self.add_user)
            self.view.userTable.cellDoubleClicked.connect(self.edit_user)
    
    def show_dialog(self):
        """Hiển thị dialog và trả về kết quả"""
        return self.view.exec_() == QDialog.Accepted
    
    def get_updated_user_data(self):
        """Lấy thông tin người dùng đã cập nhật"""
        return self.model.get_user(self.username)
    
    def load_users(self):
        """Tải danh sách người dùng"""
        users_data = self.model.get_all_users()
        self.view.update_user_table(users_data)
    
    def change_password(self):
        """Thay đổi mật khẩu"""
        old_password = self.view.oldPasswordInput.text()
        new_password = self.view.newPasswordInput.text()
        confirm_password = self.view.confirmPasswordInput.text()
        
        if not old_password or not new_password or not confirm_password:
            QMessageBox.warning(self.view, "Lỗi", "Vui lòng nhập đầy đủ thông tin")
            return
        
        if new_password != confirm_password:
            QMessageBox.warning(self.view, "Lỗi", "Mật khẩu mới không khớp")
            return
        
        success, message = self.model.change_password(self.username, old_password, new_password)
        
        if success:
            QMessageBox.information(self.view, "Thành công", message)
            # Xóa input
            self.view.oldPasswordInput.clear()
            self.view.newPasswordInput.clear()
            self.view.confirmPasswordInput.clear()
        else:
            QMessageBox.warning(self.view, "Lỗi", message)
    
    def update_api(self):
        """Cập nhật API keys"""
        api_key = self.view.apiKeyInput.text()
        api_secret = self.view.apiSecretInput.text()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self.view, "Lỗi", "Vui lòng nhập đầy đủ thông tin")
            return
        
        # Cập nhật API
        success, message = self.model.update_user(self.username, {
            "api_key": api_key,
            "api_secret": api_secret
        })
        
        if success:
            QMessageBox.information(self.view, "Thành công", "Cập nhật API thành công")
            # Cập nhật dữ liệu người dùng
            self.user_data = self.model.get_user(self.username)
        else:
            QMessageBox.warning(self.view, "Lỗi", message)
    
    def add_user(self):
        """Thêm người dùng mới"""
        dialog = QDialog(self.view)
        dialog.setWindowTitle("Thêm người dùng")
        dialog.setFixedSize(300, 220)
        
        layout = QFormLayout()
        
        username_input = QLineEdit()
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        confirm_password_input = QLineEdit()
        confirm_password_input.setEchoMode(QLineEdit.Password)
        
        role_combo = QComboBox()
        role_combo.addItems(["user", "admin"])
        
        buttons = QHBoxLayout()
        save_button = QPushButton("Lưu")
        cancel_button = QPushButton("Hủy")
        
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        
        layout.addRow("Tên đăng nhập:", username_input)
        layout.addRow("Mật khẩu:", password_input)
        layout.addRow("Xác nhận mật khẩu:", confirm_password_input)
        layout.addRow("Vai trò:", role_combo)
        layout.addRow("", buttons)
        
        dialog.setLayout(layout)
        
        def save_new_user():
            new_username = username_input.text()
            new_password = password_input.text()
            confirm_password = confirm_password_input.text()
            new_role = role_combo.currentText()
            
            if not new_username:
                QMessageBox.warning(dialog, "Lỗi", "Vui lòng nhập tên đăng nhập")
                return
                
            if not new_password:
                QMessageBox.warning(dialog, "Lỗi", "Vui lòng nhập mật khẩu")
                return
                
            if new_password != confirm_password:
                QMessageBox.warning(dialog, "Lỗi", "Xác nhận mật khẩu không khớp")
                return
            
            success, message = self.model.add_user(new_username, new_password, new_role)
            
            if success:
                self.load_users()
                dialog.accept()
                QMessageBox.information(self.view, "Thành công", message)
            else:
                QMessageBox.warning(dialog, "Lỗi", message)
        
        save_button.clicked.connect(save_new_user)
        cancel_button.clicked.connect(dialog.reject)
        
        dialog.exec_()
    
    def edit_user(self, row, column):
        """Chỉnh sửa thông tin người dùng"""
        username = self.view.userTable.item(row, 0).text()
        
        # Không cho phép sửa tài khoản admin gốc
        if username == "admin" and self.username != "admin":
            QMessageBox.warning(self.view, "Lỗi", "Bạn không có quyền sửa tài khoản admin gốc")
            return
        
        user = self.model.get_user(username)
        if not user:
            QMessageBox.warning(self.view, "Lỗi", "Người dùng không tồn tại")
            return
        
        dialog = QDialog(self.view)
        dialog.setWindowTitle(f"Chỉnh sửa người dùng: {username}")
        dialog.setFixedSize(400, 250)
        
        layout = QFormLayout()
        
        # Mật khẩu mới (không bắt buộc)
        new_password_input = QLineEdit()
        new_password_input.setPlaceholderText("Để trống nếu không đổi")
        new_password_input.setEchoMode(QLineEdit.Password)
        
        # Vai trò
        role_combo = QComboBox()
        role_combo.addItems(["user", "admin"])
        role_combo.setCurrentText(user["role"])
        
        # Nếu là admin gốc, không cho đổi vai trò
        if username == "admin":
            role_combo.setEnabled(False)
        
        layout.addRow("Mật khẩu mới:", new_password_input)
        layout.addRow("Vai trò:", role_combo)
        
        # Nút Reset API key
        reset_api_button = QPushButton("Reset API key")
        layout.addRow("", reset_api_button)
        
        # Nút xóa người dùng
        delete_button = QPushButton("Xóa người dùng")
        delete_button.setStyleSheet("background-color: #f44336; color: white;")
        layout.addRow("", delete_button)
        
        # Nếu là admin gốc, không cho xóa
        if username == "admin":
            delete_button.setEnabled(False)
        
        # Nút lưu/hủy
        buttons = QHBoxLayout()
        save_button = QPushButton("Lưu thay đổi")
        cancel_button = QPushButton("Hủy")
        
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addRow("", buttons)
        
        dialog.setLayout(layout)
        
        def save_changes():
            new_password = new_password_input.text()
            new_role = role_combo.currentText()
            
            data = {"role": new_role}
            if new_password:
                data["password"] = new_password
            
            success, message = self.model.update_user(username, data)
            
            if success:
                self.load_users()
                dialog.accept()
                QMessageBox.information(self.view, "Thành công", "Cập nhật thông tin người dùng thành công")
            else:
                QMessageBox.warning(dialog, "Lỗi", message)
        
        def reset_api():
            success, message = self.model.reset_api_key(username)
            
            if success:
                QMessageBox.information(dialog, "Thành công", message)
            else:
                QMessageBox.warning(dialog, "Lỗi", message)
        
        def delete_user():
            if username == "admin":
                QMessageBox.warning(dialog, "Lỗi", "Không thể xóa tài khoản admin gốc")
                return
            
            confirm = QMessageBox.question(
                dialog, 
                'Xác nhận xóa người dùng', 
                f'Bạn có chắc chắn muốn xóa người dùng {username} không? Dữ liệu giao dịch của người dùng này cũng sẽ bị xóa.',
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            ) == QMessageBox.Yes
            
            if not confirm:
                return
            
            success, message = self.model.delete_user(username)
            
            if success:
                # Xóa dữ liệu giao dịch
                self.trade_model.delete_user_trades(username)
                
                self.load_users()
                dialog.accept()
                QMessageBox.information(self.view, "Thành công", message)
            else:
                QMessageBox.warning(dialog, "Lỗi", message)
        
        # Kết nối signals
        save_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)
        reset_api_button.clicked.connect(reset_api)
        delete_button.clicked.connect(delete_user)
        
        dialog.exec_()