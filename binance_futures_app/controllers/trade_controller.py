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
            return []
        
        binance_trades = []
        
        try:
            # 1. Lấy vị thế đang mở
            logging.info("Đang lấy thông tin vị thế...")
            positions = self.binance_client.get_positions()
            logging.info(f"Đã nhận {len(positions)} vị thế")
            # Xử lý positions
            positions = self.binance_client.get_positions()
            for position in positions:
                position_amount = float(position.get('positionAmt', 0))
                if position_amount == 0:
                    continue
                
                symbol = position['symbol']
                entry_price = float(position['entryPrice'])
                mark_price = float(position.get('markPrice', 0))
                unrealized_pnl = float(position.get('unRealizedProfit', 0))
                side = "BUY" if position_amount > 0 else "SELL"
                position_id = f"POS_{symbol}_{side}"
                
                binance_trades.append({
                    'id': position_id,
                    'symbol': symbol,
                    'side': side,
                    'price': entry_price,
                    'quantity': abs(position_amount),
                    'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'status': "OPEN",
                    'pnl': unrealized_pnl,
                    'source': "Binance",
                    'order_type': "Đang mở"
                })
            
            # 2. Lấy lệnh đang mở
            logging.info("Đang lấy thông tin lệnh đang mở...")
            open_orders = self.binance_client.get_open_orders()
            logging.info(f"Đã nhận {len(open_orders)} lệnh đang mở")
            
            # Xử lý open_orders
            open_orders = self.binance_client.get_open_orders()
            for order in open_orders:
                order_id = str(order.get('orderId', ''))
                symbol = order['symbol']
                side = order['side']
                order_type = order['type']
                price = float(order.get('price', 0))
                if price == 0 and 'avgPrice' in order:
                    price = float(order['avgPrice'])
                qty = float(order.get('origQty', 0))
                status = order['status']
                time_str = datetime.datetime.fromtimestamp(int(order['time']) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                
                # Kiểm tra loại lệnh để xác định SL/TP
                if "STOP" in order_type or order_type == "STOP_MARKET":
                    type_label = "Stop Loss"
                elif "TAKE_PROFIT" in order_type:
                    type_label = "Take Profit"
                elif order_type == "LIMIT":
                    type_label = "Limit"
                elif order_type == "MARKET":
                    type_label = "Market"
                else:
                    type_label = order_type
                
                binance_trades.append({
                    'id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': qty,
                    'timestamp': time_str,
                    'status': status,
                    'pnl': 0,
                    'source': "Binance",
                    'order_type': type_label
                })
            
            # 3. Lấy lịch sử giao dịch
            symbol = self.view.symbolComboBox.currentText()
            logging.info(f"Đang lấy lịch sử giao dịch cho {symbol}...")
            trade_history = self.binance_client.get_trade_history(symbol)
            logging.info(f"Đã nhận {len(trade_history)} giao dịch lịch sử")
            
            # Xử lý trade_history
            symbol = self.view.symbolComboBox.currentText()
            trade_history = self.binance_client.get_trade_history(symbol)
            
            for trade in trade_history:
                trade_id = str(trade.get('id', ''))
                order_id = str(trade.get('orderId', ''))
                
                # Kiểm tra trùng lặp
                duplicate = False
                for existing_trade in binance_trades:
                    if existing_trade['id'] == order_id:
                        duplicate = True
                        break
                
                if duplicate:
                    continue
                
                symbol = trade['symbol']
                side = "BUY" if trade['isBuyer'] else "SELL"
                price = float(trade.get('price', 0))
                qty = float(trade.get('qty', 0))
                realized_pnl = float(trade.get('realizedPnl', 0))
                time_str = datetime.datetime.fromtimestamp(int(trade['time']) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                
                binance_trades.append({
                    'id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': qty,
                    'timestamp': time_str,
                    'status': "FILLED",
                    'pnl': realized_pnl,
                    'source': "Binance",
                    'order_type': "Đã đóng"
                })
            
            return binance_trades
            
        except Exception as e:
            logging.error(f"Lỗi khi lấy dữ liệu từ Binance: {e}")
            return []