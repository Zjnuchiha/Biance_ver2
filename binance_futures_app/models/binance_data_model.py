import time
import threading
import logging
import datetime
from collections import defaultdict

from binance.um_futures import UMFutures
from binance.error import ClientError
from config.logging_config import setup_logger

# Tạo logger cho module này
logger = setup_logger(__name__)

class BinanceDataModel:
    """
    Model tập trung xử lý tất cả các tương tác với Binance API.
    Lưu trữ dữ liệu trong bộ nhớ cục bộ và tự động cập nhật sau mỗi khoảng thời gian.
    """

    def __init__(self, api_key="", api_secret="", update_interval=15):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.update_interval = update_interval  # Khoảng thời gian cập nhật (giây)
        
        # Lưu trữ dữ liệu trong bộ nhớ
        self.cache = {
            "last_update": 0,
            "tickers": {},
            "account": None,
            "positions": [],
            "open_orders": defaultdict(list),
            "exchange_info": None,
            "server_time": 0
        }
        
        # Khóa để đồng bộ hóa truy cập vào cache
        self.cache_lock = threading.RLock()
        
        # Cờ để kiểm soát vòng lặp cập nhật
        self.running = False
        self.update_thread = None
        
        # Kết nối nếu có API key
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
            
            # Cập nhật server time
            with self.cache_lock:
                self.cache["server_time"] = server_time['serverTime']
            
            # Nếu kết nối thành công, bắt đầu thread cập nhật
            self.start_update_thread()
            
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
    
    def reconnect(self):
        """Kết nối lại nếu mất kết nối"""
        if not self.is_connected():
            return self.connect()
        return True, "Đã kết nối"
    
    def update_api_credentials(self, api_key, api_secret):
        """Cập nhật thông tin API và kết nối lại"""
        # Dừng thread cập nhật hiện tại nếu có
        self.stop_update_thread()
        
        # Cập nhật thông tin API
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Kết nối lại
        return self.connect()
    
    def start_update_thread(self):
        """Bắt đầu thread cập nhật dữ liệu tự động"""
        if self.running:
            return  # Thread đã chạy
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        logger.info("Đã bắt đầu thread cập nhật dữ liệu tự động")
    
    def stop_update_thread(self):
        """Dừng thread cập nhật dữ liệu"""
        if not self.running:
            return  # Thread không chạy
        
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)  # Chờ tối đa 2 giây
            logger.info("Đã dừng thread cập nhật dữ liệu")
    
    def _update_loop(self):
        """Vòng lặp cập nhật dữ liệu tự động"""
        while self.running:
            try:
                if self.is_connected():
                    # Cập nhật tất cả dữ liệu cần thiết
                    self._update_all_data()
                    
                    # Cập nhật thời gian cập nhật cuối cùng
                    with self.cache_lock:
                        self.cache["last_update"] = time.time()
                else:
                    # Nếu không có kết nối, thử kết nối lại
                    logger.warning("Không có kết nối Binance, đang thử kết nối lại...")
                    self.reconnect()
            except Exception as e:
                logger.error(f"Lỗi trong vòng lặp cập nhật: {e}")
            
            # Ngủ đến khoảng thời gian cập nhật tiếp theo
            time.sleep(self.update_interval)
    
    def _update_all_data(self):
        """Cập nhật tất cả các loại dữ liệu cần thiết"""
        try:
            # Cập nhật server time
            self._update_server_time()
            
            # Cập nhật exchange info (nếu chưa có hoặc đã quá hạn - 1 giờ)
            if (not self.cache["exchange_info"] or 
                time.time() - self.cache.get("exchange_info_time", 0) > 3600):
                self._update_exchange_info()
            
            # Cập nhật thông tin tài khoản
            self._update_account_info()
            
            # Cập nhật vị thế
            self._update_positions()
            
            # Cập nhật lệnh đang mở cho các cặp giao dịch phổ biến
            self._update_open_orders()
            
            logger.debug("Đã cập nhật tất cả dữ liệu Binance")
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật dữ liệu: {e}")
    
    def _update_server_time(self):
        """Cập nhật thời gian máy chủ"""
        try:
            server_time = self.client.time()
            with self.cache_lock:
                self.cache["server_time"] = server_time['serverTime']
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật thời gian máy chủ: {e}")
    
    def _update_exchange_info(self):
        """Cập nhật thông tin sàn giao dịch"""
        try:
            exchange_info = self.client.exchange_info()
            with self.cache_lock:
                self.cache["exchange_info"] = exchange_info
                self.cache["exchange_info_time"] = time.time()
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật thông tin sàn giao dịch: {e}")
    
    def _update_account_info(self):
        """Cập nhật thông tin tài khoản"""
        try:
            account_info = self.client.account()
            with self.cache_lock:
                self.cache["account"] = account_info
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật thông tin tài khoản: {e}")
    
    def _update_positions(self):
        """Cập nhật thông tin vị thế"""
        try:
            positions = self.client.get_position_risk()
            with self.cache_lock:
                self.cache["positions"] = positions
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật thông tin vị thế: {e}")
    
    def _update_ticker(self, symbol):
        """Cập nhật giá cho một cặp giao dịch cụ thể"""
        try:
            ticker = self.client.ticker_price(symbol=symbol)
            with self.cache_lock:
                self.cache["tickers"][symbol] = {
                    "price": float(ticker["price"]),
                    "time": time.time()
                }
            return float(ticker["price"])
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật giá {symbol}: {e}")
            return None
    
    def _update_open_orders(self):
        """Cập nhật danh sách lệnh đang mở cho các cặp giao dịch phổ biến"""
        try:
            # Danh sách cặp giao dịch phổ biến
            popular_symbols = [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT", 
                "XRPUSDT", "SOLUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"
            ]
            
            # Lấy vị thế có số lượng > 0 để lấy thêm lệnh cho các cặp này
            with self.cache_lock:
                positions = self.cache["positions"]
            
            # Thêm các cặp có vị thế vào danh sách cần lấy lệnh
            active_symbols = set(popular_symbols)
            for position in positions:
                if float(position.get('positionAmt', 0)) != 0:
                    active_symbols.add(position['symbol'])
            
            # Làm mới danh sách lệnh đang mở
            with self.cache_lock:
                self.cache["open_orders"] = defaultdict(list)
            
            # Cập nhật lệnh cho từng cặp giao dịch
            for symbol in active_symbols:
                try:
                    orders = self.client.get_open_orders(symbol=symbol)
                    with self.cache_lock:
                        self.cache["open_orders"][symbol] = orders
                except Exception as e:
                    logger.warning(f"Không thể lấy lệnh đang mở cho {symbol}: {e}")
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật lệnh đang mở: {e}")
    
    def get_ticker_price(self, symbol):
        """Lấy giá hiện tại cho một cặp giao dịch"""
        if not self.is_connected():
            return None
        
        with self.cache_lock:
            # Kiểm tra xem có dữ liệu trong cache và còn mới không
            if (symbol in self.cache["tickers"] and 
                time.time() - self.cache["tickers"][symbol]["time"] < 5):  # Coi dữ liệu giá cũ hơn 5 giây là hết hạn
                return self.cache["tickers"][symbol]["price"]
        
        # Nếu không có dữ liệu hoặc dữ liệu đã cũ, cập nhật mới
        return self._update_ticker(symbol)
    
    def get_multiple_ticker_prices(self, symbols):
        """Lấy giá cho nhiều cặp giao dịch"""
        if not self.is_connected():
            return {}
        
        result = {}
        for symbol in symbols:
            price = self.get_ticker_price(symbol)
            if price:
                result[symbol] = price
        
        return result
    
    def get_account_balance(self):
        """Lấy thông tin số dư tài khoản"""
        if not self.is_connected():
            return None
        
        with self.cache_lock:
            return self.cache["account"]
    
    def get_positions(self):
        """Lấy danh sách vị thế"""
        if not self.is_connected():
            return []
        
        with self.cache_lock:
            return self.cache["positions"]
    
    def get_open_orders(self, symbol=None):
        """Lấy danh sách lệnh đang mở"""
        if not self.is_connected():
            return []
        
        with self.cache_lock:
            if symbol:
                return self.cache["open_orders"].get(symbol, [])
            else:
                # Trả về tất cả lệnh từ tất cả các cặp
                all_orders = []
                for orders in self.cache["open_orders"].values():
                    all_orders.extend(orders)
                return all_orders
    
    def get_exchange_info(self):
        """Lấy thông tin sàn giao dịch"""
        if not self.is_connected():
            return None
        
        with self.cache_lock:
            return self.cache["exchange_info"]
    
    def get_symbol_info(self, symbol):
        """Lấy thông tin chi tiết cho một cặp giao dịch cụ thể"""
        exchange_info = self.get_exchange_info()
        if not exchange_info:
            return None
        
        for sym_info in exchange_info["symbols"]:
            if sym_info["symbol"] == symbol:
                return sym_info
        
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
            symbol_info = self.get_symbol_info(symbol)
            precision = 5  # Giá trị mặc định
            
            if symbol_info:
                # Tìm bộ lọc LOT_SIZE để xác định độ chính xác của số lượng
                for filter_info in symbol_info['filters']:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        # Lấy stepSize và tính toán độ chính xác
                        step_size = float(filter_info['stepSize'])
                        precision = len(str(step_size).rstrip('0').split('.')[-1])
                        break
            
            return round(quantity, precision)
        except Exception as e:
            logger.error(f"Lỗi khi tính toán số lượng lệnh: {e}")
            return None
    
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
            stop_order_id = None
            if stop_loss > 0:
                # Sử dụng giá trị thực thay vì tính theo phần trăm
                stop_price = stop_loss
                stop_params = {
                    'symbol': symbol,
                    'side': "SELL" if side == "BUY" else "BUY",
                    'type': 'STOP_MARKET',
                    'stopPrice': stop_price,
                    'closePosition': True
                }
                
                stop_response = self.client.new_order(**stop_params)
                stop_order_id = stop_response.get('orderId')
            
            # Đặt take profit nếu cần
            take_profit_order_id = None
            if take_profit > 0:
                # Sử dụng giá trị thực thay vì tính theo phần trăm
                take_profit_price = take_profit
                take_profit_params = {
                    'symbol': symbol,
                    'side': "SELL" if side == "BUY" else "BUY",
                    'type': 'TAKE_PROFIT_MARKET',
                    'stopPrice': take_profit_price,
                    'closePosition': True
                }
                
                tp_response = self.client.new_order(**take_profit_params)
                take_profit_order_id = tp_response.get('orderId')
            
            # Chuyển đổi thời gian từ Binance (UTC) sang múi giờ +7
            timestamp_str = ""
            if 'updateTime' in order_response:
                # Tạo đối tượng datetime ở múi giờ UTC
                utc_time = datetime.datetime.fromtimestamp(order_response['updateTime'] / 1000, datetime.timezone.utc)
                # Chuyển đổi sang múi giờ +7
                local_time = utc_time.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
                # Định dạng thành chuỗi
                timestamp_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
            elif 'transactTime' in order_response:
                # Tạo đối tượng datetime ở múi giờ UTC
                utc_time = datetime.datetime.fromtimestamp(order_response['transactTime'] / 1000, datetime.timezone.utc)
                # Chuyển đổi sang múi giờ +7
                local_time = utc_time.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
                # Định dạng thành chuỗi
                timestamp_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Nếu không có thông tin thời gian từ Binance, sử dụng thời gian hiện tại
                timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Tạo đối tượng kết quả
            trade_info = {
                'id': order_response['orderId'],
                'symbol': symbol,
                'side': side,
                'price': current_price,
                'quantity': quantity,
                'timestamp': timestamp_str,
                'status': order_response['status'],
                'pnl': 0,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': leverage,
                'updateTime': order_response.get('updateTime'),
                'transactTime': order_response.get('transactTime')
            }
            
            # Cập nhật cache - Đảm bảo lệnh mới được thêm vào cache
            self._update_positions()  # Cập nhật vị thế
            self._update_open_orders()  # Cập nhật lệnh đang mở
            
            return True, trade_info
        except ClientError as e:
            return False, f"Lỗi Binance API: {e}"
        except Exception as e:
            return False, f"Lỗi không xác định: {e}"
    
    def close_position(self, symbol, side):
        """Đóng vị thế đang mở"""
        if not self.is_connected():
            return False, "Không có kết nối Binance"
        
        try:
            # Kiểm tra vị thế hiện tại
            positions = self.get_positions()
            position_exists = False
            position_amount = 0
            
            for position in positions:
                if position['symbol'] == symbol:
                    position_amount = float(position.get('positionAmt', 0))
                    if position_amount != 0:
                        position_exists = True
                        break
            
            if not position_exists:
                return False, f"Không tìm thấy vị thế mở cho {symbol}"
            
            # Chiều đóng vị thế ngược với chiều của vị thế
            close_side = "SELL" if side == "BUY" else "BUY"
            
            # Khối lượng để đóng (đảo dấu để đóng vị thế)
            quantity = abs(position_amount)
            
            # Đóng vị thế sử dụng MARKET_ORDER với reduceOnly=True
            result = self.client.new_order(
                symbol=symbol,
                side=close_side,
                type="MARKET",
                quantity=quantity,
                reduceOnly=True  # Đảm bảo lệnh chỉ đóng vị thế, không mở vị thế mới
            )
            
            # Hủy tất cả lệnh đang mở cho symbol
            try:
                self.client.cancel_all_open_orders(symbol=symbol)
            except Exception as e:
                logger.warning(f"Lưu ý khi hủy tất cả lệnh: {e}")
            
            # Cập nhật dữ liệu
            self._update_positions()
            self._update_open_orders()
            
            return True, result
        except ClientError as e:
            return False, f"Lỗi Binance API khi đóng vị thế: {e}"
        except Exception as e:
            return False, f"Lỗi không xác định khi đóng vị thế: {e}"
    
    def get_trade_history(self, symbol, limit=50):
        """Lấy lịch sử giao dịch"""
        if not self.is_connected():
            return []
        
        try:
            # Thời gian trong 7 ngày gần đây
            end_time = int(time.time() * 1000)
            start_time = end_time - (7 * 24 * 60 * 60 * 1000)  # 7 ngày
            
            return self.client.get_account_trades(
                symbol=symbol,
                startTime=start_time,
                endTime=end_time,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Lỗi khi lấy lịch sử giao dịch: {e}")
            return []
    
    def validate_api_permissions(self):
        """Kiểm tra quyền của API key"""
        if not self.is_connected():
            return False, "Không có kết nối đến Binance API"
        
        try:
            # Kiểm tra quyền thông qua account API
            account_info = self.get_account_balance()
            
            if not account_info or 'canTrade' not in account_info:
                return False, "API key không có quyền giao dịch"
            
            if not account_info['canTrade']:
                return False, "API key không được phép giao dịch"
            
            # Thử tạo lệnh test để kiểm tra quyền trading
            try:
                test_order = self.client.new_order_test(
                    symbol="BTCUSDT",
                    side="BUY",
                    type="LIMIT",
                    timeInForce="GTC",
                    quantity=0.001,
                    price=1
                )
                return True, "API key hợp lệ và có đủ quyền"
            except ClientError as e:
                if "-2015" in str(e):
                    return False, "API key không có quyền trading"
                return False, f"Lỗi kiểm tra quyền trading: {str(e)}"
        except ClientError as e:
            return False, f"Lỗi khi kiểm tra API key: {e}"
        except Exception as e:
            return False, f"Lỗi không xác định khi kiểm tra API key: {e}"

    def get_klines(self, symbol, interval, limit=200):
        """Lấy dữ liệu nến (K-Line)"""
        if not self.is_connected():
            return None
            
        try:
            klines = self.client.klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except Exception as e:
            logger.error(f"Lỗi khi lấy dữ liệu nến: {e}")
            return None
            
    def check_connection(self):
        """Kiểm tra kết nối và quyền của API key"""
        if not self.api_key or not self.api_secret:
            return False, "Chưa cấu hình API key"
            
        try:
            # Kiểm tra trạng thái tài khoản
            account_info = self.get_account_balance()
            if not account_info:
                return False, "Không thể kết nối đến Binance API"
                
            # Kiểm tra quyền trading
            return self.validate_api_permissions()
        except Exception as e:
            logger.error(f"Lỗi kiểm tra kết nối: {str(e)}")
            return False, f"Lỗi không xác định: {str(e)}"