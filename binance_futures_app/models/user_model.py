import os
import json
import hashlib
from config.config import USERS_FILE

class UserModel:
    def __init__(self):
        self.users_file = USERS_FILE
        self._ensure_users_file_exists()
    
    def _ensure_users_file_exists(self):
        """Đảm bảo file users.json tồn tại với dữ liệu khởi tạo"""
        if not os.path.exists(os.path.dirname(self.users_file)):
            os.makedirs(os.path.dirname(self.users_file))
        
        if not os.path.exists(self.users_file):
            with open(self.users_file, "w") as f:
                # Tạo tài khoản admin mặc định
                admin_pass = hashlib.sha256("@homonkey283".encode()).hexdigest()
                users_data = {"admin": {"password": admin_pass, "role": "admin", "api_key": "", "api_secret": ""}}
                json.dump(users_data, f)
    
    def get_all_users(self):
        """Lấy tất cả người dùng"""
        try:
            with open(self.users_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Nếu file không tồn tại hoặc rỗng, tạo dữ liệu mặc định
            admin_pass = hashlib.sha256("@homonkey283".encode()).hexdigest()
            users_data = {"admin": {"password": admin_pass, "role": "admin", "api_key": "", "api_secret": ""}}
            
            # Lưu dữ liệu mặc định vào file
            with open(self.users_file, "w") as f:
                json.dump(users_data, f, indent=4)
            
            return users_data
    
    def get_user(self, username):
        """Lấy thông tin người dùng theo username"""
        users = self.get_all_users()
        return users.get(username)
    
    def authenticate(self, username, password):
        """Xác thực người dùng"""
        users = self.get_all_users()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username in users and users[username]["password"] == password_hash:
            return True
        return False
    
    def add_user(self, username, password, role="user"):
        """Thêm người dùng mới"""
        if not username or not password:
            return False, "Vui lòng nhập đầy đủ thông tin"
        
        users = self.get_all_users()
        
        if username in users:
            return False, "Tên đăng nhập đã tồn tại"
        
        # Mã hóa mật khẩu
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Thêm người dùng mới
        users[username] = {
            "password": password_hash,
            "role": role,
            "api_key": "",
            "api_secret": ""
        }
        
        with open(self.users_file, "w") as f:
            json.dump(users, f)
        
        return True, "Đã thêm người dùng thành công"
    
    def update_user(self, username, data):
        """Cập nhật thông tin người dùng"""
        users = self.get_all_users()
        
        if username not in users:
            return False, "Người dùng không tồn tại"
        
        # Cập nhật thông tin
        if "password" in data and data["password"]:
            # Mã hóa mật khẩu mới
            password_hash = hashlib.sha256(data["password"].encode()).hexdigest()
            users[username]["password"] = password_hash
        
        if "role" in data:
            users[username]["role"] = data["role"]
        
        if "api_key" in data:
            users[username]["api_key"] = data["api_key"]
        
        if "api_secret" in data:
            users[username]["api_secret"] = data["api_secret"]
        
        with open(self.users_file, "w") as f:
            json.dump(users, f)
        
        return True, "Đã cập nhật thông tin người dùng"
    
    def change_password(self, username, old_password, new_password):
        """Thay đổi mật khẩu"""
        if not self.authenticate(username, old_password):
            return False, "Mật khẩu hiện tại không chính xác"
        
        users = self.get_all_users()
        
        # Mã hóa mật khẩu mới
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        users[username]["password"] = password_hash
        
        with open(self.users_file, "w") as f:
            json.dump(users, f)
        
        return True, "Thay đổi mật khẩu thành công"
    
    def delete_user(self, username):
        """Xóa người dùng"""
        if username == "admin":
            return False, "Không thể xóa tài khoản admin gốc"
        
        users = self.get_all_users()
        
        if username not in users:
            return False, "Người dùng không tồn tại"
        
        del users[username]
        
        with open(self.users_file, "w") as f:
            json.dump(users, f)
        
        return True, "Đã xóa người dùng"
    
    def reset_api_key(self, username):
        """Reset API key của người dùng"""
        users = self.get_all_users()
        
        if username not in users:
            return False, "Người dùng không tồn tại"
        
        users[username]["api_key"] = ""
        users[username]["api_secret"] = ""
        
        with open(self.users_file, "w") as f:
            json.dump(users, f)
        
        return True, f"Đã reset API key của người dùng {username}"