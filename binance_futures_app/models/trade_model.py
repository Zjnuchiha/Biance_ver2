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
        rows = self.db.fetch_all("SELECT * FROM trades WHERE username = ? ORDER BY timestamp DESC", (username,))

        for row in rows:
            trade = dict(row)
            # Fetch full trade details from Binance if needed
            trade_details = self.fetch_trade_from_binance(trade['order_id'])
            if trade_details:
                trade.update(trade_details) #Update with details from Binance
            trades.append(trade)

        return trades

    def add_trade(self, username, trade_info):
        """Thêm một giao dịch mới - chỉ lưu ID lệnh và thông tin cơ bản"""
        try:
            # Lưu ID giao dịch vào cơ sở dữ liệu
            trade_id = trade_info.get('order_id', None) # Assuming order_id is provided
            if trade_id is None:
                logger.error("Order ID is missing for trade")
                return False
            symbol = trade_info.get('symbol', '')
            side = trade_info.get('side', '')
            timestamp = trade_info.get('timestamp', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            source = trade_info.get('source', 'Manual')


            query = """
                    INSERT INTO trades (
                        id, username, symbol, side, entry_time, source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """
            values = (trade_id, username, symbol, side, timestamp, source)
            success = self.db.execute_query(query, values)

            if success:
                logger.info(f"Added trade with ID {trade_id} for user {username}")
                return True
            else:
                logger.error(f"Failed to add trade for user {username}")
                return False

        except Exception as e:
            logger.exception(f"Error adding trade: {e}")
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
            "SELECT * FROM trades WHERE username = ? AND status = 'OPEN' ORDER BY timestamp DESC", 
            (username,)
        )

        for row in rows:
            trades.append(dict(row))

        return trades

    def fetch_trade_from_binance(self, order_id):
        """Placeholder: Fetch trade details from Binance API using order_id"""
        # Replace this with actual Binance API call
        # ... Binance API interaction ...
        # Example return (replace with actual data)
        return {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 20000,
            "quantity": 0.1,
            "amount": 2000,
            "leverage": 10,
            "entry_time": "2024-10-27 10:00:00",
            "exit_time": "2024-10-27 11:00:00",
            "exit_price": 21000,
            "pnl": 1000,
            "status": "CLOSED",
            "note": "Test trade"
        }