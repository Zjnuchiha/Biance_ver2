import time
import logging
from binance.um_futures import UMFutures
from binance.error import ClientError
import datetime
class BinanceClientModel:
    def __init__(self, api_key="", api_secret=""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        
        if api_key and api_secret:
            self.connect()
    
    def connect(self):
        """Kết nối tới Binance API"""
        if not self.api_key or not self.api_secret:
            return False, "API key hoặc API secret không được cung cấp"
        
        try:
            self.client = UMFutures(key=self.api_key, secret=self.api_secret)
            
            # Kiểm tra kết nối
            server_time = self.client.time()
            if 'serverTime' not in server_time:
                self.client = None
                return False, "Không thể lấy thông tin từ API Binance"
            
            return True, "Đã kết nối tới Binance API"
        except ClientError as e:
            self.client = None
            return False, f"Không thể kết nối tới Binance: {e}"
        except Exception as e:
            self.client = None
            return False, f"Lỗi không xác định: {e}"
    
    def is_connected(self):
        """Kiểm tra kết nối có sẵn sàng không"""
        return self.client is not None
    
    def get_ticker_price(self, symbol):
        """Lấy giá hiện tại của một cặp giao dịch"""
        if not self.is_connected():
            return None
        
        try:
            ticker_response = self.client.ticker_price(symbol=symbol)
            return float(ticker_response['price'])
        except Exception as e:
            logging.error(f"Lỗi khi lấy giá: {e}")
            return None
    
    def get_account_balance(self):
        """Lấy số dư tài khoản"""
        if not self.is_connected():
            return None
        
        try:
            account_response = self.client.account()
            return account_response
        except Exception as e:
            logging.error(f"Lỗi khi lấy số dư: {e}")
            return None
    
    def get_open_orders(self):
        """Lấy danh sách lệnh đang mở"""
        if not self.is_connected():
            return []
        
        try:
            return self.client.get_open_orders()
        except Exception as e:
            logging.error(f"Lỗi khi lấy lệnh mở: {e}")
            return []
    
    def get_positions(self):
        """Lấy danh sách vị thế"""
        if not self.is_connected():
            logging.warning("Không thể lấy vị thế - API không được kết nối")
            return []
        
        try:
            logging.info("Đang gọi API lấy vị thế...")
            positions = self.client.get_position_risk()
            logging.info(f"Đã nhận {len(positions)} vị thế từ API")
            return positions
        except ClientError as e:
            error_msg = str(e)
            logging.error(f"Lỗi ClientError khi lấy vị thế: {error_msg}")
            
            # Xử lý các lỗi cụ thể
            if "Invalid API-key" in error_msg:
                logging.error("API key không hợp lệ")
            elif "Signature for this request is not valid" in error_msg:
                logging.error("API secret không chính xác")
            elif "API-key has no permission" in error_msg:
                logging.error("API key không có quyền đọc thông tin vị thế")
            
            return []
        except Exception as e:
            logging.error(f"Lỗi khi lấy vị thế: {e}", exc_info=True)
            return []
    
    def get_trade_history(self, symbol, limit=50):
        """Lấy lịch sử giao dịch"""
        if not self.is_connected():
            return []
        
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (7 * 24 * 60 * 60 * 1000)  # 7 ngày
            
            return self.client.get_account_trades(
                symbol=symbol,
                startTime=start_time,
                endTime=end_time,
                limit=limit
            )
        except Exception as e:
            logging.error(f"Lỗi khi lấy lịch sử giao dịch: {e}")
            return []
    
    def place_order(self, symbol, side, quantity, leverage=1, stop_loss=0, take_profit=0):
        """Đặt lệnh giao dịch"""
        if not self.is_connected():
            return False, "Không có kết nối Binance"
        
        try:
            # Lấy giá hiện tại
            current_price = self.get_ticker_price(symbol)
            if not current_price:
                return False, "Không thể lấy giá hiện tại"
            
            # Đặt đòn bẩy
            self.client.change_leverage(symbol=symbol, leverage=leverage)
            
            # Đặt lệnh market
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity
            }
            
            order_response = self.client.new_order(**order_params)
            
            # Đặt stop loss nếu cần
            if stop_loss > 0:
                stop_price = current_price * (1 - stop_loss / 100) if side == "BUY" else current_price * (1 + stop_loss / 100)
                stop_params = {
                    'symbol': symbol,
                    'side': "SELL" if side == "BUY" else "BUY",
                    'type': 'STOP_MARKET',
                    'stopPrice': stop_price,
                    'closePosition': True
                }
                
                self.client.new_order(**stop_params)
            
            # Đặt take profit nếu cần
            if take_profit > 0:
                take_profit_price = current_price * (1 + take_profit / 100) if side == "BUY" else current_price * (1 - take_profit / 100)
                take_profit_params = {
                    'symbol': symbol,
                    'side': "SELL" if side == "BUY" else "BUY",
                    'type': 'TAKE_PROFIT_MARKET',
                    'stopPrice': take_profit_price,
                    'closePosition': True
                }
                
                self.client.new_order(**take_profit_params)
            
            # Tạo đối tượng kết quả
            trade_info = {
                'id': order_response['orderId'],
                'symbol': symbol,
                'side': side,
                'price': current_price,
                'quantity': quantity,
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': order_response['status'],
                'pnl': 0,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
            return True, trade_info
        except ClientError as e:
            return False, f"Lỗi Binance API: {e}"
        except Exception as e:
            return False, f"Lỗi không xác định: {e}"
    
    def get_exchange_info(self):
        """Lấy thông tin Exchange"""
        if not self.is_connected():
            return None
        
        try:
            return self.client.exchange_info()
        except Exception as e:
            logging.error(f"Lỗi khi lấy thông tin exchange: {e}")
            return None
    
    def calculate_order_quantity(self, symbol, amount):
        """Tính toán số lượng chính xác cho một lệnh"""
        if not self.is_connected():
            return None
        
        try:
            # Lấy giá hiện tại
            current_price = self.get_ticker_price(symbol)
            if not current_price:
                return None
            
            # Tính toán số lượng
            quantity = amount / current_price
            
            # Lấy thông tin symbol để biết chính xác precision
            exchange_info = self.get_exchange_info()
            precision = 5  # Giá trị mặc định
            
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    # Tìm bộ lọc LOT_SIZE để xác định độ chính xác của số lượng
                    for filter_info in symbol_info['filters']:
                        if filter_info['filterType'] == 'LOT_SIZE':
                            # Lấy stepSize và tính toán độ chính xác
                            step_size = float(filter_info['stepSize'])
                            precision = len(str(step_size).rstrip('0').split('.')[-1])
                            break
                    break
            
            return round(quantity, precision)
        except Exception as e:
            logging.error(f"Lỗi khi tính toán số lượng: {e}")
            return None
    def validate_api_permissions(self):
        """Kiểm tra quyền của API key"""
        if not self.is_connected():
            return False, "Không có kết nối đến Binance API"
        
        try:
            # Kiểm tra quyền thông qua account API
            account_info = self.client.account()
            
            if 'canTrade' not in account_info:
                return False, "API key không có quyền giao dịch"
            
            if not account_info['canTrade']:
                return False, "API key không được phép giao dịch"
            
            # Thử lấy vị thế để kiểm tra quyền truy cập futures
            positions = self.client.get_position_risk()
            
            return True, "API key hợp lệ và có đủ quyền"
        except ClientError as e:
            error_code = str(e).split(':')[0] if ':' in str(e) else "Unknown"
            if "-2015" in error_code:
                return False, "API key không hợp lệ hoặc đã hết hạn"
            elif "-2014" in error_code:
                return False, "API secret không chính xác"
            elif "-2021" in error_code or "-2022" in error_code:
                return False, "API key không có quyền truy cập futures"
            else:
                return False, f"Lỗi khi kiểm tra API key: {e}"
        except Exception as e:
            return False, f"Lỗi không xác định khi kiểm tra API key: {e}"