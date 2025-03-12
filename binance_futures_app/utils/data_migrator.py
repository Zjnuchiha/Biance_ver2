import os
import json
import hashlib
from config.config import USERS_FILE, TRADES_FILE, SETTINGS_FILE
from utils.database_manager import DatabaseManager
from config.logging_config import setup_logger

# Tạo logger cho module này
logger = setup_logger(__name__)

class DataMigrator:
    """Công cụ di chuyển dữ liệu từ JSON sang SQLite"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def migrate_users(self):
        """Di chuyển dữ liệu người dùng từ JSON sang SQLite"""
        try:
            # Kiểm tra xem file users.json có tồn tại không
            if not os.path.exists(USERS_FILE):
                logger.info("File users.json không tồn tại, bỏ qua di chuyển dữ liệu người dùng")
                return True
            
            # Đọc dữ liệu từ file JSON
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users_data = json.load(f)
            
            logger.info(f"Đọc được {len(users_data)} người dùng từ file JSON")
            
            # Di chuyển dữ liệu vào SQLite
            for username, user_data in users_data.items():
                # Kiểm tra xem người dùng đã tồn tại trong database chưa
                row = self.db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
                
                if row:
                    # Người dùng đã tồn tại, cập nhật thông tin
                    self.db.execute_query(
                        "UPDATE users SET password = ?, role = ?, api_key = ?, api_secret = ? WHERE username = ?",
                        (
                            user_data.get("password", ""),
                            user_data.get("role", "user"),
                            user_data.get("api_key", ""),
                            user_data.get("api_secret", ""),
                            username
                        )
                    )
                else:
                    # Thêm người dùng mới
                    self.db.execute_query(
                        "INSERT INTO users (username, password, role, api_key, api_secret) VALUES (?, ?, ?, ?, ?)",
                        (
                            username,
                            user_data.get("password", ""),
                            user_data.get("role", "user"),
                            user_data.get("api_key", ""),
                            user_data.get("api_secret", "")
                        )
                    )
            
            logger.info("Di chuyển dữ liệu người dùng thành công")
            return True
        
        except Exception as e:
            logger.error(f"Lỗi khi di chuyển dữ liệu người dùng: {e}")
            return False
    
    def migrate_trades(self):
        """Di chuyển dữ liệu giao dịch từ JSON sang SQLite"""
        try:
            # Kiểm tra xem file trades.json có tồn tại không
            if not os.path.exists(TRADES_FILE):
                logger.info("File trades.json không tồn tại, bỏ qua di chuyển dữ liệu giao dịch")
                return True
            
            # Đọc dữ liệu từ file JSON
            with open(TRADES_FILE, "r", encoding="utf-8") as f:
                trades_data = json.load(f)
            
            trade_count = 0
            # Di chuyển dữ liệu vào SQLite
            for username, user_trades in trades_data.items():
                for trade_info in user_trades:
                    # Tạo truy vấn SQL động dựa trên các trường có trong trade_info
                    fields = ["username"]
                    values = [username]
                    placeholders = ["?"]
                    
                    for key, value in trade_info.items():
                        fields.append(key)
                        values.append(value)
                        placeholders.append("?")
                    
                    query = f"INSERT INTO trades ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                    self.db.execute_query(query, values)
                    trade_count += 1
            
            logger.info(f"Di chuyển {trade_count} giao dịch thành công")
            return True
        
        except Exception as e:
            logger.error(f"Lỗi khi di chuyển dữ liệu giao dịch: {e}")
            return False
    
    def migrate_settings(self):
        """Di chuyển dữ liệu cài đặt từ JSON sang SQLite"""
        try:
            # Kiểm tra xem file settings.json có tồn tại không
            if not os.path.exists(SETTINGS_FILE):
                logger.info("File settings.json không tồn tại, bỏ qua di chuyển dữ liệu cài đặt")
                return True
            
            # Đọc dữ liệu từ file JSON
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
            
            settings_count = 0
            # Di chuyển dữ liệu vào SQLite
            for username, user_settings in settings_data.items():
                for key, value in user_settings.items():
                    # Chuyển đổi giá trị thành chuỗi
                    str_value = str(value)
                    
                    # Thêm cài đặt vào database
                    self.db.execute_query(
                        "INSERT INTO settings (username, key, value) VALUES (?, ?, ?)",
                        (username, key, str_value)
                    )
                    settings_count += 1
            
            logger.info(f"Di chuyển {settings_count} cài đặt thành công")
            return True
        
        except Exception as e:
            logger.error(f"Lỗi khi di chuyển dữ liệu cài đặt: {e}")
            return False
    
    def run_migration(self):
        """Thực hiện toàn bộ quá trình di chuyển dữ liệu"""
        logger.info("Bắt đầu quá trình di chuyển dữ liệu từ JSON sang SQLite")
        
        # Di chuyển dữ liệu người dùng
        users_ok = self.migrate_users()
        
        # Di chuyển dữ liệu giao dịch
        trades_ok = self.migrate_trades()
        
        # Di chuyển dữ liệu cài đặt
        settings_ok = self.migrate_settings()
        
        if users_ok and trades_ok and settings_ok:
            logger.info("Di chuyển dữ liệu thành công")
            return True
        else:
            logger.error("Có lỗi xảy ra trong quá trình di chuyển dữ liệu")
            return False