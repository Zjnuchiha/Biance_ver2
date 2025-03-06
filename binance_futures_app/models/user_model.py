
import hashlib
import os
import json
from config.config import USERS_FILE, DATABASE_PATH
from utils.database_manager import DatabaseManager
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class UserModel:
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_all_users(self):
        """Lấy tất cả người dùng"""
        users = {}
        rows = self.db.fetch_all("SELECT * FROM users")
        for row in rows:
            users[row['username']] = {
                "password": row['password'],
                "role": row['role'],
                "api_key": row['api_key'] or "",
                "api_secret": row['api_secret'] or ""
            }
        return users
    
    def get_user(self, username):
        """Lấy thông tin người dùng theo username"""
        row = self.db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if row:
            return {
                "password": row['password'],
                "role": row['role'],
                "api_key": row['api_key'] or "",
                "api_secret": row['api_secret'] or ""
            }
        return None
    
    def authenticate(self, username, password):
        """Xác thực người dùng"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        row = self.db.fetch_one(
            "SELECT * FROM users WHERE username = ? AND password = ?", 
            (username, password_hash)
        )
        return row is not None
    
    def add_user(self, username, password, role="user"):
        """Thêm người dùng mới"""
        if not username or not password:
            return False, "Vui lòng nhập đầy đủ thông tin"
        
        # Kiểm tra username đã tồn tại chưa
        existing_user = self.db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if existing_user:
            return False, "Tên đăng nhập đã tồn tại"
        
        # Mã hóa mật khẩu
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Thêm người dùng mới
        success = self.db.execute_query(
            "INSERT INTO users (username, password, role, api_key, api_secret) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, role, "", "")
        )
        
        if success:
            return True, "Đã thêm người dùng thành công"
        else:
            return False, "Lỗi khi thêm người dùng"
    
    def update_user(self, username, data):
        """Cập nhật thông tin người dùng"""
        # Kiểm tra username tồn tại
        existing_user = self.db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if not existing_user:
            return False, "Người dùng không tồn tại"
        
        # Xây dựng câu lệnh SQL và tham số tương ứng
        update_fields = []
        params = []
        
        if "password" in data and data["password"]:
            # Mã hóa mật khẩu mới
            password_hash = hashlib.sha256(data["password"].encode()).hexdigest()
            update_fields.append("password = ?")
            params.append(password_hash)
        
        if "role" in data:
            update_fields.append("role = ?")
            params.append(data["role"])
        
        if "api_key" in data:
            update_fields.append("api_key = ?")
            params.append(data["api_key"])
        
        if "api_secret" in data:
            update_fields.append("api_secret = ?")
            params.append(data["api_secret"])
        
        if not update_fields:
            return True, "Không có thông tin cần cập nhật"
        
        # Thêm tham số username vào cuối
        params.append(username)
        
        # Thực thi truy vấn update
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE username = ?"
        success = self.db.execute_query(query, params)
        
        if success:
            return True, "Đã cập nhật thông tin người dùng"
        else:
            return False, "Lỗi khi cập nhật thông tin người dùng"
    
    def change_password(self, username, old_password, new_password):
        """Thay đổi mật khẩu"""
        if not self.authenticate(username, old_password):
            return False, "Mật khẩu hiện tại không chính xác"
        
        # Mã hóa mật khẩu mới
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        
        success = self.db.execute_query(
            "UPDATE users SET password = ? WHERE username = ?",
            (password_hash, username)
        )
        
        if success:
            return True, "Thay đổi mật khẩu thành công"
        else:
            return False, "Lỗi khi thay đổi mật khẩu"
    
    def delete_user(self, username):
        """Xóa người dùng"""
        if username == "admin":
            return False, "Không thể xóa tài khoản admin gốc"
        
        # Kiểm tra username tồn tại
        existing_user = self.db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if not existing_user:
            return False, "Người dùng không tồn tại"
        
        # Xóa cài đặt của người dùng
        self.db.execute_query("DELETE FROM settings WHERE username = ?", (username,))
        
        # Xóa giao dịch của người dùng
        self.db.execute_query("DELETE FROM trades WHERE username = ?", (username,))
        
        # Xóa người dùng
        success = self.db.execute_query("DELETE FROM users WHERE username = ?", (username,))
        
        if success:
            return True, "Đã xóa người dùng"
        else:
            return False, "Lỗi khi xóa người dùng"
    
    def reset_api_key(self, username):
        """Reset API key của người dùng"""
        success = self.db.execute_query(
            "UPDATE users SET api_key = '', api_secret = '' WHERE username = ?",
            (username,)
        )
        
        if success:
            return True, f"Đã reset API key của người dùng {username}"
        else:
            return False, f"Lỗi khi reset API key của người dùng {username}"
