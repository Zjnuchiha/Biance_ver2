import time
from PyQt5.QtCore import QThread, pyqtSignal
from config.logging_config import setup_logger

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
        
    def run(self):
        while self.running:
            try:
                # Cập nhật giá
                price = self.binance_client.get_ticker_price(self.symbol)
                if price:
                    self.price_update.emit(str(price))
                
                # Cập nhật số dư Futures
                try:
                    # Lấy thông tin tài khoản futures
                    account_response = self.binance_client.get_account_balance()
                    
                    if account_response and 'assets' in account_response:
                        # Tạo dict để lưu số dư
                        balances = {}
                        
                        # Tách base asset từ symbol (ví dụ: BTC từ BTCUSDT)
                        base_asset = self.symbol.replace('USDT', '')
                        
                        # Lấy số dư USDT (tiền tệ chính trong Futures)
                        usdt_balance = 0
                        
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
                    error_msg = f"Lỗi khi lấy số dư: {e}"
                    logging.error(error_msg)
                    self.error_signal.emit(error_msg)
                
            except Exception as e:
                error_msg = f"Lỗi cập nhật giá: {e}"
                logging.error(error_msg)
                self.error_signal.emit(error_msg)
                
                # Giảm tần suất cập nhật khi có lỗi
                time.sleep(5)
            
            # Tần suất cập nhật bình thường
            time.sleep(1)
    
    def stop(self):
        self.running = False