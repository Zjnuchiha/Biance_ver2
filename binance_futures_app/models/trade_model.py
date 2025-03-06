import os
import json
import datetime
from config.config import TRADES_FILE

class TradeModel:
    def __init__(self):
        self.trades_file = TRADES_FILE
        self._ensure_trades_file_exists()
    
    def _ensure_trades_file_exists(self):
        """Đảm bảo file trades.json tồn tại"""
        if not os.path.exists(os.path.dirname(self.trades_file)):
            os.makedirs(os.path.dirname(self.trades_file))
        
        if not os.path.exists(self.trades_file):
            with open(self.trades_file, "w") as f:
                json.dump({}, f)
    
    def get_user_trades(self, username):
        """Lấy lịch sử giao dịch của người dùng"""
        with open(self.trades_file, "r") as f:
            trades_data = json.load(f)
        
        if username not in trades_data:
            trades_data[username] = []
            with open(self.trades_file, "w") as f:
                json.dump(trades_data, f)
        
        return trades_data[username]
    
    def add_trade(self, username, trade_info):
        """Thêm một giao dịch mới"""
        with open(self.trades_file, "r") as f:
            trades_data = json.load(f)
        
        if username not in trades_data:
            trades_data[username] = []
        
        trades_data[username].append(trade_info)
        
        with open(self.trades_file, "w") as f:
            json.dump(trades_data, f)
        
        return True
    
    def delete_user_trades(self, username):
        """Xóa tất cả giao dịch của một người dùng"""
        with open(self.trades_file, "r") as f:
            trades_data = json.load(f)
        
        if username in trades_data:
            del trades_data[username]
            
            with open(self.trades_file, "w") as f:
                json.dump(trades_data, f)
            
            return True
        
        return False