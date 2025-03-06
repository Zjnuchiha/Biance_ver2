
import os
import sqlite3
from config.config import DATABASE_PATH
import logging
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class DatabaseManager:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        """Đảm bảo database tồn tại và tạo thư mục chứa nếu cần"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # Kết nối đến database sẽ tự động tạo file nếu chưa tồn tại
        conn = self.get_connection()
        try:
            # Tạo bảng users nếu chưa tồn tại
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                api_key TEXT,
                api_secret TEXT
            )
            ''')
            
            # Tạo bảng trades nếu chưa tồn tại
            conn.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                amount REAL NOT NULL,
                leverage INTEGER NOT NULL,
                order_id TEXT,
                entry_time INTEGER NOT NULL,
                exit_time INTEGER,
                exit_price REAL,
                pnl REAL,
                status TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY (username) REFERENCES users(username)
            )
            ''')
            
            # Tạo bảng settings nếu chưa tồn tại
            conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                username TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (username, key),
                FOREIGN KEY (username) REFERENCES users(username)
            )
            ''')
            
            # Kiểm tra xem đã có user admin chưa
            cursor = conn.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            count = cursor.fetchone()[0]
            
            # Nếu chưa có, tạo user admin mặc định
            if count == 0:
                import hashlib
                admin_pass = hashlib.sha256("@homonkey283".encode()).hexdigest()
                conn.execute('''
                INSERT INTO users (username, password, role, api_key, api_secret)
                VALUES (?, ?, ?, ?, ?)
                ''', ('admin', admin_pass, 'admin', '', ''))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_connection(self):
        """Trả về kết nối đến database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Để kết quả truy vấn trả về dưới dạng dictionary
            return conn
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def execute_query(self, query, params=None):
        """Thực thi truy vấn không trả về dữ liệu"""
        conn = self.get_connection()
        try:
            if params:
                conn.execute(query, params)
            else:
                conn.execute(query)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error executing query: {query}, error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def fetch_one(self, query, params=None):
        """Thực thi truy vấn và trả về một bản ghi"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error executing fetch_one query: {query}, error: {e}")
            return None
        finally:
            conn.close()
    
    def fetch_all(self, query, params=None):
        """Thực thi truy vấn và trả về tất cả bản ghi"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error executing fetch_all query: {query}, error: {e}")
            return []
        finally:
            conn.close()
