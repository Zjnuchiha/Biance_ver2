import time
import datetime
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from config.logging_config import setup_logger
from binance.error import ClientError
import logging
from models import binance_data_singleton
from .auto_trader import AutoTrader

# Tạo logger cho module này
logger = setup_logger(__name__)

class TradeController(QObject):
    def __init__(self, view, binance_client_model, trade_model, username):
        super().__init__()
        self.view = view
        self.binance_client = binance_client_model
        self.trade_model = trade_model
        self.username = username
        self.auto_trader = None
        # Kết nối tín hiệu đóng vị thế
        self.view.close_position_signal.connect(self.close_position)
        # Lấy tham chiếu đến data model
        self.data_model = binance_data_singleton.get_instance()

    def place_order(self, side):
        """Đặt lệnh giao dịch"""
        if not self.binance_client.is_connected():
            self.view.show_message("Lỗi", "Không có kết nối Binance", QMessageBox.Warning)
            return

        symbol = self.view.symbolComboBox.currentText()
        amount = self.view.amountSpinBox.value()
        leverage = self.view.leverageSpinBox.value()
        stop_loss = self.view.stopLossSpinBox.value()  # Giá trị thực, có thể là 0 (trống)
        take_profit = self.view.takeProfitSpinBox.value()  # Giá trị thực, có thể là 0 (trống)

        try:
            # Tính toán số lượng
            quantity = self.data_model.calculate_order_quantity(symbol, amount)

            if not quantity:
                self.view.show_message("Lỗi", "Không thể tính toán số lượng lệnh", QMessageBox.Warning)
                return

            # Lấy giá hiện tại
            current_price = self.data_model.get_ticker_price(symbol)
            if not current_price:
                self.view.show_message("Lỗi", "Không thể lấy giá hiện tại", QMessageBox.Warning)
                return

            # Xác nhận giao dịch
            confirm = self.view.confirm_dialog(
                f'Xác nhận {side}', 
                f'Bạn có chắc chắn muốn đặt lệnh {side} {quantity} {symbol} với giá {current_price} không?\n'
                f'Đòn bẩy: {leverage}x\n'
                f'Stop Loss: {stop_loss}\n'
                f'Take Profit: {take_profit}'
            )

            if not confirm:
                return

            # Đặt lệnh
            success, result = self.data_model.place_order(
                symbol, side, quantity, leverage, stop_loss, take_profit
            )

            if success:
                # Lưu thông tin giao dịch với đòn bẩy
                # Kết quả từ place_order() đã được chuyển đổi sang múi giờ +7
                minimal_trade_info = {
                    'id': result.get('id', str(int(time.time()))),
                    'symbol': symbol,
                    'side': side,
                    'source': 'Manual',
                    'leverage': leverage,  # Thêm thông tin đòn bẩy
                    'timestamp': result.get('timestamp', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))  # Sử dụng thời gian đã được chuyển đổi
                }

                # Lưu vào model
                self.trade_model.add_trade(self.username, minimal_trade_info)

                # Cập nhật giao diện
                self.view.show_message(
                    "Thành công", 
                    f"Đã đặt lệnh {side} thành công\n"
                    f"Giá: {current_price}\n"
                    f"Đòn bẩy: {leverage}x\n"
                    f"SL: {stop_loss}\n"
                    f"TP: {take_profit}"
                )
            else:
                self.view.show_message("Lỗi", result, QMessageBox.Warning)

        except Exception as e:
            error_msg = f"Lỗi khi đặt lệnh: {e}"
            logger.error(error_msg)
            self.view.show_message("Lỗi", error_msg, QMessageBox.Warning)

    def start_auto_trading(self, symbol, timeframe, amount, leverage, stop_loss, trading_method="Đường Base Line"):
        """Bắt đầu giao dịch tự động với phương pháp được chọn"""
        if self.auto_trader and self.auto_trader.isRunning():
            logger.warning("AutoTrader is already running, stopping it first")
            self.stop_auto_trading()
            # Đợi một chút để thread dừng
            time.sleep(0.5)

        try:
            # Tạo đối tượng AutoTrader
            self.auto_trader = AutoTrader(
                self.binance_client,
                symbol,
                timeframe,
                amount,
                leverage,
                stop_loss,
                trading_method
            )
            
            # Kết nối các tín hiệu
            self.auto_trader.trade_update.connect(self.handle_auto_trade)
            self.auto_trader.status_update.connect(self.update_auto_trading_status)
            
            # Kết nối tín hiệu đóng vị thế mới
            self.auto_trader.close_position_signal.connect(self.close_position)
            
            # Bắt đầu thread
            self.auto_trader.start()

            # Cập nhật trạng thái
            self.view.auto_trading_status.setText(f"Giao dịch tự động: Đã bật - {symbol} - {timeframe} - {trading_method}")
            logger.info(f"AutoTrader started for {symbol} with timeframe {timeframe} using method {trading_method}")
        except Exception as e:
            logger.error(f"Failed to start AutoTrader: {e}")
            raise

    def stop_auto_trading(self):
        """Dừng giao dịch tự động an toàn"""
        if self.auto_trader:
            logger.info("Stopping auto trading...")
            self.auto_trader.stop()
            
            # Sử dụng QTimer để tránh chặn UI thread
            from PyQt5.QtCore import QTimer
            
            def check_thread_finished():
                if not self.auto_trader.isRunning():
                    logger.info("AutoTrader thread stopped successfully")
                    self.auto_trader = None
                    # Cập nhật UI sau khi thread đã dừng hoàn toàn
                    self.view.auto_trading_status.setText("Giao dịch tự động: Đã tắt")
                else:
                    # Nếu thread vẫn chạy sau 5 giây, hiển thị thông báo và thử terminate
                    if hasattr(self, '_stop_attempts'):
                        self._stop_attempts -= 1
                        if self._stop_attempts <= 0:
                            logger.warning("Force terminating AutoTrader thread")
                            self.auto_trader.terminate()
                            self.auto_trader = None
                            self.view.auto_trading_status.setText("Giao dịch tự động: Đã tắt (forced)")
                            return
                    
                    # Kiểm tra lại sau 500ms
                    QTimer.singleShot(500, check_thread_finished)
            
            self._stop_attempts = 10  # Số lần thử tối đa (5 giây)
            check_thread_finished()
        else:
            self.view.auto_trading_status.setText("Giao dịch tự động: Đã tắt")

    def handle_auto_trade(self, trade_info):
        """Xử lý giao dịch tự động"""
        # Lưu vào model
        self.trade_model.add_trade(self.username, trade_info)
        
        # Cập nhật danh sách giao dịch
        if hasattr(self, 'main_controller'):
            self.main_controller.load_trades()

    def update_auto_trading_status(self, status):
        """Cập nhật trạng thái giao dịch tự động"""
        self.view.auto_trading_status.setText(f"Giao dịch tự động: {status}")

    # Lấy thông tin giao dịch
    def get_binance_trades(self):
        """Lấy lịch sử giao dịch từ Binance API"""
        if not self.binance_client.is_connected():
            logger.warning("Cannot connect to Binance API - Check API key and secret")
            return []
        
        try:
            # Lấy vị thế đang mở từ BinanceDataModel
            positions = self.data_model.get_positions()
            # Lấy thông tin tài khoản để đảm bảo có đòn bẩy
            account_info = self.data_model.get_account_balance()
            
            # Tạo dict chứa thông tin đòn bẩy
            leverage_info = {}
            if account_info and 'positions' in account_info:
                leverage_info = {p["symbol"]: int(p["leverage"]) for p in account_info["positions"]}
            
            binance_trades = []
            
            for position in positions:
                # Chỉ xem xét các vị thế có số lượng khác 0
                position_amount = float(position.get('positionAmt', 0))
                if position_amount == 0:
                    continue
                
                symbol = position['symbol']
                entry_price = float(position['entryPrice'])
                unrealized_pnl = float(position.get('unRealizedProfit', 0))
                side = "BUY" if position_amount > 0 else "SELL"
                
                # Sử dụng ID mặc định trước (sẽ được cập nhật nếu tìm thấy lệnh)
                position_id = f"POS_{symbol}_{side}"
                
                # Đòn bẩy
                leverage = leverage_info.get(symbol, 1)
                
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
                    'order_type': "Đang mở",
                    'leverage': leverage
                }
                
                # Tìm lệnh SL/TP cho vị thế này
                try:
                    # Lấy lệnh đang mở cho symbol
                    open_orders = self.data_model.get_open_orders(symbol)
                    
                    # Lọc lệnh đóng vị thế
                    active_orders = []
                    for order in open_orders:
                        order_side = order.get('side', '')
                        is_closing_order = (side == "BUY" and order_side == "SELL") or (side == "SELL" and order_side == "BUY")
                        
                        # Kiểm tra xem lệnh có closePosition=True không
                        is_close_position = order.get('closePosition', False)
                        
                        # Nếu không có thuộc tính closePosition, kiểm tra type
                        if not is_close_position:
                            order_type = order.get('type', '')
                            is_close_position = order_type in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]
                        
                        # Lệnh phải đang mở (status = NEW)
                        if is_closing_order and order.get('status', '') == 'NEW' and is_close_position:
                            active_orders.append(order)
                    
                    # Nếu tìm thấy lệnh, sử dụng orderId của lệnh đầu tiên làm ID
                    if active_orders:
                        # Sử dụng orderId của lệnh đầu tiên
                        order_id = active_orders[0].get('orderId')
                        if order_id:
                            trade_info['id'] = str(order_id)
                    
                    # Tìm SL/TP
                    for order in active_orders:
                        order_type = order.get('type', '')
                        
                        if order_type == "STOP_MARKET":
                            sl_price = float(order.get('stopPrice', 0))
                            # Tính % SL
                            if side == "BUY":  # Long position
                                sl_percent = round(((entry_price - sl_price) / entry_price) * 100, 2)
                            else:  # Short position
                                sl_percent = round(((sl_price - entry_price) / entry_price) * 100, 2)
                                
                            # Lưu cả giá thực và phần trăm
                            trade_info['stop_loss'] = f"{sl_price} ({sl_percent}%)"
                            
                        elif order_type == "TAKE_PROFIT_MARKET":
                            tp_price = float(order.get('stopPrice', 0))
                            # Tính % TP
                            if side == "BUY":  # Long position
                                tp_percent = round(((tp_price - entry_price) / entry_price) * 100, 2)
                            else:  # Short position
                                tp_percent = round(((entry_price - tp_price) / entry_price) * 100, 2)
                                
                            # Lưu cả giá thực và phần trăm
                            trade_info['take_profit'] = f"{tp_price} ({tp_percent}%)"
                
                except Exception as e:
                    logger.error(f"Error finding SL/TP for {symbol}: {e}")
                
                binance_trades.append(trade_info)
            
            return binance_trades
            
        except Exception as e:
            logger.error(f"Overall error fetching data from Binance: {e}", exc_info=True)
            return []

    # Đóng vị thế (và cả stoploss/takeprofit)
    def close_position(self, trade_id, symbol, side):
        """Đóng vị thế đang mở và xử lý lệnh liên quan - phiên bản tối ưu"""
        from PyQt5.QtCore import QTimer
        
        logger.info(f"Closing position: ID={trade_id}, Symbol={symbol}, Side={side}")
        
        if not self.binance_client.is_connected():
            self.view.show_message("Lỗi", "Không có kết nối Binance", QMessageBox.Warning)
            return
        
        try:
            # Đóng vị thế sử dụng BinanceDataModel
            success, result = self.data_model.close_position(symbol, side)
            
            if success:
                # Hiển thị thông báo thành công
                self.view.show_message(
                    "Thành công", 
                    f"Đã đóng vị thế {symbol} ({side}) thành công\n"
                    f"Order ID: {result.get('orderId', 'N/A')}"
                )
                
                # Vô hiệu hóa nút đóng vị thế
                self.disable_close_button(trade_id)
                
                # Tạo timer để cập nhật lại danh sách giao dịch sau khi đóng
                QTimer.singleShot(2000, self.force_refresh_trades)
            else:
                # Xử lý lỗi
                error_msg = str(result)
                if "Order does not exist" in error_msg:
                    self.view.show_message("Thông báo", "Vị thế đã được đóng hoặc không tồn tại.", QMessageBox.Information)
                    QTimer.singleShot(1000, self.force_refresh_trades)
                else:
                    self.view.show_message("Lỗi", f"Không thể đóng vị thế: {result}", QMessageBox.Critical)
                
        except Exception as e:
            error_msg = f"Lỗi xử lý: {e}"
            logger.error(error_msg, exc_info=True)
            self.view.show_message("Lỗi", error_msg, QMessageBox.Warning)

    def disable_close_button(self, trade_id):
        """Vô hiệu hóa nút đóng vị thế cho giao dịch có ID cụ thể"""
        try:
            # Tìm và vô hiệu hóa nút trong bảng giao dịch
            for row in range(self.view.tradeTable.rowCount()):
                item = self.view.tradeTable.item(row, 0)  # Cột ID
                if item and item.text() == str(trade_id):
                    # Tìm thấy hàng có ID trùng khớp
                    button = self.view.tradeTable.cellWidget(row, 11)  # Cột Trạng thái/Hành động
                    if button:
                        button.setEnabled(False)
                        button.setText("Đang đóng...")
                        button.setStyleSheet("background-color: #7f8c8d; color: white;")
                    break
        except Exception as e:
            logger.error(f"Error disabling close button: {e}")

    def force_refresh_trades(self):
        """Cập nhật lại danh sách giao dịch ngay lập tức"""
        try:
            # Gọi hàm load_trades của MainController
            if hasattr(self, 'main_controller'):
                # Nếu có tham chiếu trực tiếp
                self.main_controller.load_trades()
            else:
                # Nếu không có tham chiếu trực tiếp, tìm trong parent widgets
                from controllers.main_controller import MainController
                parent = getattr(self, 'parent', None)
                if parent and callable(parent) and isinstance(parent(), MainController):
                    parent().load_trades()

                # Reset bộ đếm thời gian làm mới tự động
                if hasattr(self.main_controller, 'refresh_timer'):
                    self.main_controller.refresh_timer = time.time()
        except Exception as e:
            logger.error(f"Error forcing trade refresh: {e}")

    def refresh_trades(self):
        """Cập nhật lại danh sách giao dịch"""
        try:
            # Nếu TradeController có tham chiếu đến MainController
            from controllers.main_controller import MainController
            if hasattr(self, 'main_controller') and isinstance(self.main_controller, MainController):
                self.main_controller.load_trades()
            else:
                # Tìm MainController trong các đối tượng cha
                parent = self.view.parent()
                while parent is not None:
                    if isinstance(parent, MainController):
                        parent.load_trades()
                        break
                    parent = parent.parent()

                # Nếu không tìm thấy, thử phương pháp cuối cùng
                from PyQt5.QtWidgets import QApplication
                main_window = QApplication.activeWindow()
                if hasattr(main_window, 'load_trades'):
                    main_window.load_trades()
        except Exception as e:
            logger.error(f"Error refreshing trades: {e}", exc_info=True)
    
    def remove_position_from_table(self, trade_id):
        """Xóa vị thế khỏi bảng hiển thị ngay lập tức"""
        try:
            for row in range(self.view.tradeTable.rowCount()):
                item = self.view.tradeTable.item(row, 0)  # Cột ID
                if item and item.text() == str(trade_id):
                    self.view.tradeTable.removeRow(row)
                    break
        except Exception as e:
            logger.error(f"Error removing position from table: {e}")