
import os
import json
import datetime
from config.config import TRADES_FILE, DATABASE_PATH
from utils.database_manager import DatabaseManager
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class TradeModel:
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_user_trades(self, username):
        """Lấy lịch sử giao dịch của người dùng"""
        trades = []
        rows = self.db.fetch_all("SELECT * FROM trades WHERE username = ? ORDER BY entry_time DESC", (username,))
        
        for row in rows:
            trade = dict(row)
            trades.append(trade)
        
        return trades
    
    def add_trade(self, username, trade_info):
        """Thêm một giao dịch mới"""
        fields = [
            "username", "symbol", "side", "price", "quantity", "amount", 
            "leverage", "order_id", "entry_time", "exit_time", "exit_price", 
            "pnl", "status", "note"
        ]
        
        # Đảm bảo tất cả trường đều có giá trị (null nếu không có)
        values = []
        placeholders = []
        
        for field in fields:
            if field in trade_info or field == "username":
                if field == "username":
                    values.append(username)
                else:
                    values.append(trade_info.get(field))
                placeholders.append("?")
            else:
                fields.remove(field)
        
        query = f"INSERT INTO trades ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        success = self.db.execute_query(query, values)
        
        if success:
            # Lấy ID của giao dịch vừa thêm
            row = self.db.fetch_one("SELECT last_insert_rowid() as id")
            if row:
                trade_id = row["id"]
                logger.info(f"Added trade with ID {trade_id} for user {username}")
            
            return True
        else:
            logger.error(f"Failed to add trade for user {username}")
            return False
    
    def update_trade(self, trade_id, trade_info):
        """Cập nhật thông tin giao dịch"""
        update_fields = []
        values = []
        
        for key, value in trade_info.items():
            if key != "id" and key != "username":  # Không cập nhật id và username
                update_fields.append(f"{key} = ?")
                values.append(value)
        
        if not update_fields:
            return False
        
        # Thêm ID vào cuối danh sách tham số
        values.append(trade_id)
        
        query = f"UPDATE trades SET {', '.join(update_fields)} WHERE id = ?"
        return self.db.execute_query(query, values)
    
    def close_trade(self, trade_id, exit_price, exit_time, pnl, status="CLOSED"):
        """Đóng một giao dịch"""
        query = """
        UPDATE trades 
        SET exit_price = ?, exit_time = ?, pnl = ?, status = ? 
        WHERE id = ?
        """
        return self.db.execute_query(query, (exit_price, exit_time, pnl, status, trade_id))
    
    def delete_trade(self, trade_id):
        """Xóa một giao dịch"""
        return self.db.execute_query("DELETE FROM trades WHERE id = ?", (trade_id,))
    
    def delete_user_trades(self, username):
        """Xóa tất cả giao dịch của một người dùng"""
        return self.db.execute_query("DELETE FROM trades WHERE username = ?", (username,))
    
    def get_trade_by_order_id(self, order_id):
        """Lấy thông tin giao dịch theo order_id"""
        row = self.db.fetch_one("SELECT * FROM trades WHERE order_id = ?", (order_id,))
        if row:
            return dict(row)
        return None
    
    def get_open_trades(self, username):
        """Lấy các giao dịch đang mở của người dùng"""
        trades = []
        rows = self.db.fetch_all(
            "SELECT * FROM trades WHERE username = ? AND status = 'OPEN' ORDER BY entry_time DESC", 
            (username,)
        )
        
        for row in rows:
            trades.append(dict(row))
        
        return trades
