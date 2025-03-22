import time
import logging
from binance.um_futures import UMFutures
from binance.error import ClientError
from binance.client import Client
import datetime

logger = logging.getLogger(__name__)
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
            logging.error(f"Error getting price: {e}")
            return None
    
    def get_account_balance(self):
        """Lấy số dư tài khoản"""
        if not self.is_connected():
            return None
        
        try:
            account_response = self.client.account()
            return account_response
        except Exception as e:
            logging.error(f"Error getting account balance: {e}")
            return None
    
    def get_open_orders(self, symbol=None):
        """Lấy danh sách lệnh đang mở"""
        if not self.is_connected():
            return []
        
        try:
            # Binance API yêu cầu tham số symbol
            if not symbol:
                # Nếu không có symbol cụ thể, lấy lệnh từ các cặp giao dịch phổ biến
                popular_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT", "XRPUSDT", 
                            "SOLUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"]
                
                all_orders = []
                for sym in popular_symbols:
                    try:
                        orders = self.client.get_open_orders(symbol=sym)
                        all_orders.extend(orders)
                    except Exception as e:
                        logging.warning(f"Unable to get open orders for {sym}: {e}")
                
                return all_orders
            else:
                # Kiểm tra symbol hợp lệ
                if not symbol or len(symbol.strip()) == 0:
                    logger.warning("Empty symbol parameter provided to get_open_orders")
                    return []
                    
                try:
                    orders = self.client.get_open_orders(symbol=symbol)
                    
                    # Lọc và chỉ giữ những order có orderId
                    valid_orders = []
                    for order in orders:
                        if order.get('orderId'):
                            valid_orders.append(order)
                        else:
                            logger.warning(f"Found order without orderId for {symbol}")
                    
                    return valid_orders
                except Exception as e:
                    logger.error(f"Error getting open orders for {symbol}: {e}")
                    return []
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    def get_positions(self):
        """Lấy danh sách vị thế với thông tin đầy đủ"""
        if not self.is_connected():
            logging.warning("Cannot get positions - API not connected")
            return []
        
        try:
            # logging.info("Calling API to get positions...")
            # Lấy thông tin vị thế
            positions = self.client.get_position_risk()
            # logging.info(f"Received {len(positions)} positions from API")
            
            # Thử lấy thêm thông tin position stop-loss và position take-profit
            try:
                account_info = self.client.account()
                if 'positions' in account_info:
                    detailed_positions = account_info['positions']
                    
                    # Bổ sung thông tin từ account_info vào positions
                    for position in positions:
                        symbol = position['symbol']
                        # Tìm thông tin chi tiết từ account_info
                        for detailed_pos in detailed_positions:
                            if detailed_pos['symbol'] == symbol:
                                # Tìm stopPrice và thêm vào position
                                if 'stopPrice' in detailed_pos and float(detailed_pos['stopPrice']) > 0:
                                    position['stopPrice'] = detailed_pos['stopPrice']
                                    logging.debug(f"Found stop price {detailed_pos['stopPrice']} for {symbol}")
                                
                                # Tìm thông tin take profit (có thể có tên trường khác)
                                for field in ['takeProfitPrice', 'tpPrice', 'takeProfitTriggerPrice']:
                                    if field in detailed_pos and float(detailed_pos.get(field, 0)) > 0:
                                        position['takeProfitPrice'] = detailed_pos[field]
                                        logging.debug(f"Found take profit {detailed_pos[field]} for {symbol}")
                                        break
            except Exception as e:
                logging.error(f"Error getting detailed position info: {e}")
                
            return positions
        except ClientError as e:
            error_msg = str(e)
            logging.error(f"ClientError when getting positions: {error_msg}")
            return []
        except Exception as e:
            logging.error(f"Error getting positions: {e}", exc_info=True)
            return []
    
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
                startTime=start_time,  # Tham số của Binance API là 'startTime' không phải 'start_time'
                endTime=end_time,      # Tham số của Binance API là 'endTime' không phải 'end_time'
                limit=limit
            )
        except Exception as e:
            logging.error(f"Error getting trade history: {e}")
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
                # Nếu không có thông tin thời gian từ Binance, sử dụng thời gian hiện tại (đã ở múi giờ cục bộ)
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
                'leverage': leverage,  # Thêm thông tin đòn bẩy
                'updateTime': order_response.get('updateTime'),  # Trả về thời gian gốc từ API
                'transactTime': order_response.get('transactTime')  # Trả về thời gian giao dịch từ API
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
            logging.error(f"Error getting exchange info: {e}")
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
            logging.error(f"Error calculating order quantity: {e}")
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
            
            # Thử tạo lệnh test để kiểm tra quyền trading
            try:
                test_order = self.client.new_order(
                    symbol="BTCUSDT",
                    side="BUY",
                    type="LIMIT",
                    timeInForce="GTC",
                    quantity=0.001,
                    price=1,
                    newOrderRespType="ACK",
                    reduceOnly=False,
                    newClientOrderId="test_order",
                    test=True  # Chế độ test, không thực sự đặt lệnh
                )
                # Nếu test thành công, có đủ quyền trading
                return True, "API key hợp lệ và có đủ quyền"
            except ClientError as trade_error:
                if "-2015" in str(trade_error):
                    return False, "API key hợp lệ nhưng không có quyền trading. Hãy kiểm tra cài đặt API key của bạn."
                else:
                    # Vẫn có vị thế, nhưng gặp lỗi khác khi test trading
                    return True, "API key có thể bị hạn chế một số quyền. Lỗi: " + str(trade_error)
                
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
    def check_connection(self):
        """Kiểm tra kết nối và quyền của API key"""
        if not self.api_key or not self.api_secret:
            return False, "Chưa cấu hình API key"
            
        try:
            # Kiểm tra trạng thái tài khoản
            account_info = self.client.account()
            
            # Kiểm tra quyền trading
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
                    logger.warning(f"API key không có quyền trading: {str(e)}")
                    return False, "API key không có quyền trading. Vui lòng kiểm tra cài đặt quyền trong tài khoản Binance của bạn."
                return False, f"Lỗi kiểm tra quyền trading: {str(e)}"
                
            return True, "API key hợp lệ" 
        except ClientError as e:
            logger.error(f"Lỗi kiểm tra kết nối: {str(e)}")
            if "-2015" in str(e):
                return False, "API key không hợp lệ hoặc không đủ quyền"
            elif "timeout" in str(e).lower():
                return False, "Kết nối tới Binance bị timeout" 
            return False, f"Lỗi kết nối: {str(e)}"
        except Exception as e:
            logger.error(f"Lỗi không xác định: {str(e)}")
            return False, f"Lỗi không xác định: {str(e)}"
