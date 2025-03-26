import logging
from models import binance_data_singleton
from config.logging_config import setup_logger

logger = setup_logger(__name__)

class BinanceClientModel:
    def __init__(self, api_key="", api_secret=""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.data_model = binance_data_singleton.get_instance(api_key, api_secret)
    
    def connect(self):
        """Kết nối tới Binance API"""
        return self.data_model.connect()
    
    def is_connected(self):
        """Kiểm tra kết nối có sẵn sàng không"""
        return self.data_model.is_connected()
    
    def get_ticker_price(self, symbol):
        """Lấy giá hiện tại của một cặp giao dịch"""
        return self.data_model.get_ticker_price(symbol)
    
    def get_account_balance(self):
        """Lấy số dư tài khoản"""
        return self.data_model.get_account_balance()
    
    def get_positions(self):
        """Lấy thông tin vị thế"""
        return self.data_model.get_positions()
    
    def get_open_orders(self, symbol=None):
        """Lấy danh sách lệnh đang mở"""
        return self.data_model.get_open_orders(symbol)
    
    def get_exchange_info(self):
        """Lấy thông tin Exchange"""
        return self.data_model.get_exchange_info()
    
    def calculate_order_quantity(self, symbol, amount):
        """Tính toán số lượng chính xác cho một lệnh"""
        return self.data_model.calculate_order_quantity(symbol, amount)
    
    def place_order(self, symbol, side, quantity, leverage=1, stop_loss=0, take_profit=0):
        """Đặt lệnh giao dịch"""
        return self.data_model.place_order(symbol, side, quantity, leverage, stop_loss, take_profit)
    
    def get_trade_history(self, symbol, limit=50):
        """Lấy lịch sử giao dịch"""
        return self.data_model.get_trade_history(symbol, limit)
    
    def validate_api_permissions(self):
        """Kiểm tra quyền của API key"""
        return self.data_model.validate_api_permissions()
    
    def check_connection(self):
        """Kiểm tra kết nối và quyền của API key"""
        return self.data_model.check_connection()