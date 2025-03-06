import os
import json
from config.config import SETTINGS_FILE

class SettingsModel:
    def __init__(self):
        self.settings_file = SETTINGS_FILE
        self._ensure_settings_file_exists()
    
    def _ensure_settings_file_exists(self):
        """Đảm bảo file settings.json tồn tại"""
        if not os.path.exists(os.path.dirname(self.settings_file)):
            os.makedirs(os.path.dirname(self.settings_file))
        
        if not os.path.exists(self.settings_file):
            default_settings = {
                "theme": "light",
                "chart_style": "candles",
                "price_alerts": [],
                "auto_refresh": True,
                "refresh_interval": 30000  # ms
            }
            
            with open(self.settings_file, "w") as f:
                json.dump(default_settings, f)
    
    def get_settings(self):
        """Lấy tất cả cài đặt"""
        try:
            with open(self.settings_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Nếu file không tồn tại hoặc rỗng, tạo dữ liệu mặc định
            default_settings = {
                "theme": "light",
                "chart_style": "candles",
                "price_alerts": [],
                "auto_refresh": True,
                "refresh_interval": 30000  # ms
            }
            
            # Lưu dữ liệu mặc định vào file
            with open(self.settings_file, "w") as f:
                json.dump(default_settings, f, indent=4)
            
            return default_settings
    
    def get_setting(self, key, default=None):
        """Lấy một cài đặt cụ thể"""
        settings = self.get_settings()
        return settings.get(key, default)
    
    def update_setting(self, key, value):
        """Cập nhật một cài đặt"""
        settings = self.get_settings()
        settings[key] = value
        
        with open(self.settings_file, "w") as f:
            json.dump(settings, f)
        
        return True
    
    def update_settings(self, settings_dict):
        """Cập nhật nhiều cài đặt cùng lúc"""
        settings = self.get_settings()
        settings.update(settings_dict)
        
        with open(self.settings_file, "w") as f:
            json.dump(settings, f)
        
        return True
import os
import json
from config.config import SETTINGS_FILE, DATABASE_PATH
from utils.database_manager import DatabaseManager
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class SettingsModel:
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_user_settings(self, username):
        """Lấy cài đặt của người dùng"""
        settings = {}
        rows = self.db.fetch_all("SELECT * FROM settings WHERE username = ?", (username,))
        
        for row in rows:
            try:
                # Thử chuyển đổi value từ chuỗi thành giá trị tương ứng
                import ast
                value = ast.literal_eval(row['value'])
            except (ValueError, SyntaxError):
                # Nếu không chuyển đổi được, giữ nguyên giá trị chuỗi
                value = row['value']
            
            settings[row['key']] = value
        
        return settings
    
    def save_user_setting(self, username, key, value):
        """Lưu một cài đặt của người dùng"""
        # Chuyển đổi giá trị thành chuỗi để lưu vào database
        str_value = str(value)
        
        # Kiểm tra xem cài đặt đã tồn tại chưa
        row = self.db.fetch_one("SELECT * FROM settings WHERE username = ? AND key = ?", (username, key))
        
        if row:
            # Cập nhật cài đặt hiện có
            success = self.db.execute_query(
                "UPDATE settings SET value = ? WHERE username = ? AND key = ?",
                (str_value, username, key)
            )
        else:
            # Thêm cài đặt mới
            success = self.db.execute_query(
                "INSERT INTO settings (username, key, value) VALUES (?, ?, ?)",
                (username, key, str_value)
            )
        
        return success
    
    def delete_user_setting(self, username, key):
        """Xóa một cài đặt của người dùng"""
        return self.db.execute_query(
            "DELETE FROM settings WHERE username = ? AND key = ?",
            (username, key)
        )
    
    def delete_all_user_settings(self, username):
        """Xóa tất cả cài đặt của người dùng"""
        return self.db.execute_query(
            "DELETE FROM settings WHERE username = ?",
            (username,)
        )
