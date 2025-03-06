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