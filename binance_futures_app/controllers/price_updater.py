import time
from PyQt5.QtCore import QThread, pyqtSignal
from config.logging_config import setup_logger
from models import binance_data_singleton

# Tạo logger cho module này
logger = setup_logger(__name__)

class PriceUpdater(QThread):
    price_update = pyqtSignal(str)
    balance_update = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, binance_client, symbol):
        super().__init__()
        self.binance_client = binance_client
        self.symbol = symbol
        self.running = True
        # Lấy tham chiếu đến data model
        self.data_model = binance_data_singleton.get_instance()
        # Thêm biến để kiểm soát tốc độ cập nhật
        self.price_update_interval = 1.0  # Cập nhật giá mỗi 1 giây
        self.balance_update_interval = 5.0  # Cập nhật số dư mỗi 5 giây
        self.last_price_update = 0
        self.last_balance_update = 0
        self.error_count = 0
        self.max_errors = 5  # Số lỗi tối đa trước khi tăng thời gian chờ

    def run(self):
        while self.running:
            current_time = time.time()
            
            try:
                # Cập nhật giá nếu đến thời điểm
                if current_time - self.last_price_update >= self.price_update_interval:
                    self.update_price()
                    self.last_price_update = current_time
                
                # Cập nhật số dư nếu đến thời điểm
                if current_time - self.last_balance_update >= self.balance_update_interval:
                    self.update_balance()
                    self.last_balance_update = current_time
                
                # Đặt lại bộ đếm lỗi nếu không có lỗi
                if self.error_count > 0:
                    self.error_count -= 1
                
            except Exception as e:
                error_msg = f"Lỗi cập nhật: {e}"
                logger.error(error_msg)
                self.error_signal.emit(error_msg)
                
                # Tăng bộ đếm lỗi và điều chỉnh khoảng thời gian nếu cần
                self.error_count += 1
                if self.error_count > self.max_errors:
                    # Tăng thời gian cập nhật để giảm tải
                    self.price_update_interval = min(5.0, self.price_update_interval * 1.5)
                    self.balance_update_interval = min(30.0, self.balance_update_interval * 1.5)
                    logger.warning(f"Điều chỉnh thời gian cập nhật: giá {self.price_update_interval}s, số dư {self.balance_update_interval}s")
                    self.error_count = 0
            
            # Ngủ một khoảng thời gian nhỏ để không tiêu tốn CPU
            time.sleep(0.1)

    def update_price(self):
        """Cập nhật giá"""
        try:
            # Sử dụng data model để lấy giá
            price = self.data_model.get_ticker_price(self.symbol)
            if price:
                self.price_update.emit(str(price))
        except Exception as e:
            logger.error(f"Error updating price: {e}")
            raise

    def update_balance(self):
        """Cập nhật số dư"""
        try:
            # Sử dụng data model để lấy thông tin tài khoản
            account_response = self.data_model.get_account_balance()
            
            if account_response and 'assets' in account_response:
                # Tạo dict để lưu số dư
                balances = {}
                
                # Tách base asset từ symbol
                base_asset = self.symbol.replace('USDT', '')
                
                # Lấy số dư của tất cả tài sản
                for asset in account_response['assets']:
                    # Lưu thông tin tài sản
                    asset_name = asset['asset']
                    wallet_balance = float(asset['walletBalance'])  # Số dư ví
                    cross_un_pnl = float(asset.get('crossUnPnl', 0))  # Lãi/lỗ chưa thực hiện
                    available_balance = float(asset.get('availableBalance', 0))  # Số dư khả dụng
                    
                    # Chỉ lưu những tài sản có số dư > 0
                    if wallet_balance > 0 or cross_un_pnl != 0:
                        balances[asset_name] = {
                            'wallet_balance': wallet_balance,
                            'unrealized_pnl': cross_un_pnl,
                            'available_balance': available_balance
                        }
                    
                    # Lưu số dư USDT
                    if asset_name == 'USDT':
                        usdt_balance = wallet_balance
                
                # Thêm thông tin tổng vào dict
                balances['total_usdt'] = usdt_balance
                
                # Gửi thông tin số dư
                self.balance_update.emit(balances)
        except Exception as e:
            logger.error(f"Error updating balance: {e}")
            raise

    def stop(self):
        """Dừng thread an toàn"""
        logger.info("Stopping price updater thread")
        self.running = False
        self.wait(1000)  # Đợi tối đa 1 giây
        if self.isRunning():
            logger.warning("Price updater thread did not stop gracefully, terminating")
            self.terminate()