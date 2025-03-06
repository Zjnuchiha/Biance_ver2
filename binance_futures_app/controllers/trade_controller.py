import time
import datetime
import logging
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

class AutoTrader(QThread):
    trade_update = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    
    def __init__(self, binance_client, symbol, timeframe, amount, leverage, stop_loss):
        super().__init__()
        self.binance_client = binance_client
        self.symbol = symbol
        self.timeframe = timeframe
        self.amount = amount
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.running = True
        
    def run(self):
        while self.running:
            try:
                self.status_update.emit("Đang phân tích thị trường...")
                
                # Lấy dữ liệu lịch sử giá với Futures Connector
                klines_response = self.binance_client.client.klines(
                    symbol=self.symbol,
                    interval=self.timeframe,
                    limit=50
                )
                
                # Phân tích kỹ thuật đơn giản (ví dụ: dựa trên SMA)
                close_prices = [float(k[4]) for k in klines_response]
                sma_5 = sum(close_prices[-5:]) / 5
                sma_10 = sum(close_prices[-10:]) / 10
                sma_20 = sum(close_prices[-20:]) / 20
                
                current_price = float(close_prices[-1])
                
                # Cập nhật trạng thái
                self.status_update.emit(f"SMA5: {sma_5:.2f}, SMA10: {sma_10:.2f}, SMA20: {sma_20:.2f}")
                
                # Chiến lược giao dịch nâng cao
                # 1. Golden Cross / Death Cross
                if sma_5 > sma_10 and close_prices[-2] < sma_5 <= close_prices[-1]:
                    # Tín hiệu mua (Golden Cross)
                    self.status_update.emit("Phát hiện tín hiệu mua (Golden Cross)...")
                    self.execute_trade("BUY", current_price)
                
                elif sma_5 < sma_10 and close_prices[-2] > sma_5 >= close_prices[-1]:
                    # Tín hiệu bán (Death Cross)
                    self.status_update.emit("Phát hiện tín hiệu bán (Death Cross)...")
                    self.execute_trade("SELL", current_price)
                
                else:
                    # Không có tín hiệu rõ ràng
                    self.status_update.emit("Đang chờ tín hiệu giao dịch...")
                
            except Exception as e:
                error_msg = f"Lỗi giao dịch tự động: {e}"
                self.status_update.emit(error_msg)
                logging.error(error_msg)
            
            # Chờ khoảng thời gian trước khi kiểm tra lại
            time_sleep = 60  # 1 phút
            if self.timeframe == '1m':
                time_sleep = 30
            elif self.timeframe == '5m':
                time_sleep = 60
            elif self.timeframe in ['15m', '30m']:
                time_sleep = 120
            else:
                time_sleep = 300
                
            self.status_update.emit(f"Nghỉ {time_sleep} giây trước lần kiểm tra tiếp theo...")
            time.sleep(time_sleep)
    
    def execute_trade(self, side, current_price):
        try:
            # Tính toán số lượng
            quantity = self.binance_client.calculate_order_quantity(self.symbol, self.amount)
            
            if not quantity:
                self.status_update.emit("Không thể tính toán số lượng lệnh")
                return
            
            self.status_update.emit(f"Đặt lệnh {side} với số lượng {quantity}...")
            
            # Đặt lệnh
            success, result = self.binance_client.place_order(
                self.symbol, side, quantity, self.leverage, self.stop_loss, 0
            )
            
            if success:
                trade_info = result
                self.status_update.emit(f"Đã đặt lệnh {side} thành công!")
                self.trade_update.emit(trade_info)
            else:
                self.status_update.emit(f"Lỗi đặt lệnh: {result}")
            
        except Exception as e:
            error_msg = f"Lỗi đặt lệnh (Hệ thống): {e}"
            self.status_update.emit(error_msg)
            logging.error(error_msg)
    
    def stop(self):
        self.running = False

class TradeController(QObject):
    def __init__(self, view, binance_client_model, trade_model, username):
        super().__init__()
        self.view = view
        self.binance_client = binance_client_model
        self.trade_model = trade_model
        self.username = username
        self.auto_trader = None
    
    def place_order(self, side):
        """Đặt lệnh giao dịch"""
        if not self.binance_client.is_connected():
            self.view.show_message("Lỗi", "Không có kết nối Binance", QMessageBox.Warning)
            return
        
        symbol = self.view.symbolComboBox.currentText()
        amount = self.view.amountSpinBox.value()
        leverage = self.view.leverageSpinBox.value()
        stop_loss = self.view.stopLossSpinBox.value()
        take_profit = self.view.takeProfitSpinBox.value()
        
        try:
            # Tính toán số lượng
            quantity = self.binance_client.calculate_order_quantity(symbol, amount)
            
            if not quantity:
                self.view.show_message("Lỗi", "Không thể tính toán số lượng lệnh", QMessageBox.Warning)
                return
            
            # Lấy giá hiện tại
            current_price = self.binance_client.get_ticker_price(symbol)
            if not current_price:
                self.view.show_message("Lỗi", "Không thể lấy giá hiện tại", QMessageBox.Warning)
                return
            
            # Xác nhận giao dịch
            confirm = self.view.confirm_dialog(
                f'Xác nhận {side}', 
                f'Bạn có chắc chắn muốn đặt lệnh {side} {quantity} {symbol} với giá {current_price} không?\n'
                f'Stop Loss: {stop_loss}%\n'
                f'Take Profit: {take_profit}%'
            )
            
            if not confirm:
                return
            
            # Đặt lệnh
            success, result = self.binance_client.place_order(
                symbol, side, quantity, leverage, stop_loss, take_profit
            )
            
            if success:
                trade_info = result
                # Lưu vào model
                self.trade_model.add_trade(self.username, trade_info)
                
                # Cập nhật giao diện
                self.view.show_message(
                    "Thành công", 
                    f"Đã đặt lệnh {side} thành công\n"
                    f"Giá: {current_price}\n"
                    f"SL: {stop_loss}%\n"
                    f"TP: {take_profit}%"
                )
            else:
                self.view.show_message("Lỗi", result, QMessageBox.Warning)
            
        except Exception as e:
            error_msg = f"Lỗi khi đặt lệnh: {e}"
            logging.error(error_msg)
            self.view.show_message("Lỗi", error_msg, QMessageBox.Warning)
    
    def start_auto_trading(self, symbol, timeframe, amount, leverage, stop_loss):
        """Bắt đầu giao dịch tự động"""
        if self.auto_trader:
            self.auto_trader.stop()
            self.auto_trader.wait()
        
        self.auto_trader = AutoTrader(
            self.binance_client,
            symbol,
            timeframe,
            amount,
            leverage,
            stop_loss
        )
        self.auto_trader.trade_update.connect(self.handle_auto_trade)
        self.auto_trader.status_update.connect(self.update_auto_trading_status)
        self.auto_trader.start()
        
        # Cập nhật trạng thái
        self.view.auto_trading_status.setText(f"Giao dịch tự động: Đã bật - {symbol} - {timeframe}")
    
    def stop_auto_trading(self):
        """Dừng giao dịch tự động"""
        if self.auto_trader:
            self.auto_trader.stop()
            self.auto_trader.wait()
            self.auto_trader = None
        
        # Cập nhật trạng thái
        self.view.auto_trading_status.setText("Giao dịch tự động: Đã tắt")
    
    def handle_auto_trade(self, trade_info):
        """Xử lý giao dịch tự động"""
        # Lưu vào model
        self.trade_model.add_trade(self.username, trade_info)
    
    def update_auto_trading_status(self, status):
        """Cập nhật trạng thái giao dịch tự động"""
        self.view.auto_trading_status.setText(f"Giao dịch tự động: {status}")
    
    def get_binance_trades(self):
        """Lấy lịch sử giao dịch từ Binance API"""
        if not self.binance_client.is_connected():
            logging.warning("Cannot connect to Binance API - Check API key and secret")
            return []
        
        binance_trades = []
        
        try:
            logging.info("=== Starting to fetch trading data from Binance ===")
            
            # 1. Lấy vị thế đang mở
            try:
                logging.info("Fetching position information...")
                positions = self.binance_client.get_positions()
                logging.info(f"Received {len(positions)} positions from Binance")
                
                for position in positions:
                    # Chỉ xem xét các vị thế có số lượng khác 0
                    position_amount = float(position.get('positionAmt', 0))
                    if position_amount == 0:
                        continue
                    
                    symbol = position['symbol']
                    entry_price = float(position['entryPrice'])
                    unrealized_pnl = float(position.get('unRealizedProfit', 0))
                    side = "BUY" if position_amount > 0 else "SELL"
                    position_id = f"POS_{symbol}_{side}"
                    
                    logging.info(f"Processing position: {symbol} {side} with PnL: {unrealized_pnl}")
                    
                    trade_info = {
                        'id': position_id,
                        'symbol': symbol,
                        'side': side,
                        'price': entry_price,
                        'quantity': abs(position_amount),
                        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'status': "OPEN",
                        'pnl': unrealized_pnl,
                        'source': "Binance",
                        'order_type': "Đang mở"  # Giữ nguyên tiếng Việt ở label hiển thị
                    }
                    
                    # Tìm lệnh SL/TP cho vị thế này
                    try:
                        orders = []
                        try:
                            orders = self.binance_client.client.get_open_orders(symbol=symbol)
                        except Exception as e:
                            logging.warning(f"Cannot get open orders for {symbol}: {e}")
                        
                        for order in orders:
                            if order.get('closePosition', False):
                                order_side = order.get('side', '')
                                order_type = order.get('type', '')
                                stop_price = float(order.get('stopPrice', 0))
                                
                                is_for_position = (side == "BUY" and order_side == "SELL") or (side == "SELL" and order_side == "BUY")
                                
                                if is_for_position and stop_price > 0:
                                    if "STOP" in order_type and "TAKE_PROFIT" not in order_type:
                                        trade_info['stop_loss'] = stop_price
                                        logging.debug(f"Found stop loss {stop_price} for {symbol} {side}")
                                    elif "TAKE_PROFIT" in order_type:
                                        trade_info['take_profit'] = stop_price
                                        logging.debug(f"Found take profit {stop_price} for {symbol} {side}")
                    except Exception as e:
                        logging.error(f"Error finding SL/TP for {symbol}: {e}")
                    
                    # HACK: Thêm giá trị SL/TP giả lập để kiểm tra UI
                    # test_ui = True  # Đặt thành False trong môi trường sản phẩm
                    # if test_ui:
                    #     trade_info['stop_loss'] = entry_price * 0.95 if side == "BUY" else entry_price * 1.05
                    #     trade_info['take_profit'] = entry_price * 1.05 if side == "BUY" else entry_price * 0.95
                    #     logging.debug(f"Added mock SL/TP for {symbol} {side}")
                    
                    binance_trades.append(trade_info)
                    
            except Exception as e:
                logging.error(f"Error getting positions: {e}", exc_info=True)
            
            # Bạn có thể bỏ qua việc lấy lệnh đang mở và lịch sử giao dịch nếu chỉ quan tâm đến SL/TP của vị thế
            
            # Log tất cả trade để debug
            for trade in binance_trades:
                logging.debug(f"Final trade: {trade}")
            
            logging.info(f"Total of {len(binance_trades)} trades fetched from Binance")
            return binance_trades
            
        except Exception as e:
            logging.error(f"Overall error fetching data from Binance: {e}", exc_info=True)
            return []