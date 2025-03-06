import time
import datetime
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from config.logging_config import setup_logger
from binance.error import ClientError
import logging

# Tạo logger cho module này
logger = setup_logger(__name__)

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
                logger.error(error_msg)

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
            logger.error(error_msg)

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
        # Kết nối tín hiệu đóng vị thế
        self.view.close_position_signal.connect(self.close_position)

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
                f'Stop Loss: {stop_loss}\n'
                f'Take Profit: {take_profit}'
            )

            if not confirm:
                return

            # Đặt lệnh
            success, result = self.binance_client.place_order(
                symbol, side, quantity, leverage, stop_loss, take_profit
            )

            if success:
                # Chỉ lưu ID và thông tin cơ bản
                minimal_trade_info = {
                    'id': result.get('id', str(int(time.time()))),
                    'symbol': symbol,
                    'side': side,
                    'source': 'Manual',
                    'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # Lưu vào model
                self.trade_model.add_trade(self.username, minimal_trade_info)

                # Cập nhật giao diện
                self.view.show_message(
                    "Thành công", 
                    f"Đã đặt lệnh {side} thành công\n"
                    f"Giá: {current_price}\n"
                    f"SL: {stop_loss}\n"
                    f"TP: {take_profit}"
                )
            else:
                self.view.show_message("Lỗi", result, QMessageBox.Warning)

        except Exception as e:
            error_msg = f"Lỗi khi đặt lệnh: {e}"
            logger.error(error_msg)
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

    # Lấy thông tin giao dịch
    def get_binance_trades(self):
        """Lấy lịch sử giao dịch từ Binance API"""
        if not self.binance_client.is_connected():
            logger.warning("Cannot connect to Binance API - Check API key and secret")
            return []

        binance_trades = []

        try:
            logger.info("=== Starting to fetch trading data from Binance ===")

            # 1. Lấy vị thế đang mở
            try:
                logger.info("Fetching position information...")
                positions = self.binance_client.get_positions()
                logger.info(f"Received {len(positions)} positions from Binance")

                # Tập hợp các symbol cần lấy thông tin giao dịch
                symbols_to_fetch = set()
                active_positions = {}

                # 1. Lọc các vị thế đang mở (positionAmt ≠ 0)
                for position in positions:
                    position_amount = float(position.get('positionAmt', 0))
                    if position_amount == 0:
                        continue

                    symbol = position['symbol']
                    symbols_to_fetch.add(symbol)
                    side = "BUY" if position_amount > 0 else "SELL"

                    # Lưu thông tin vị thế
                    if symbol not in active_positions:
                        active_positions[symbol] = []

                    active_positions[symbol].append({
                        'symbol': symbol,
                        'side': side,
                        'entry_price': float(position['entryPrice']),
                        'position_amount': position_amount,
                        'unrealized_pnl': float(position.get('unRealizedProfit', 0)),
                        'leverage': float(position.get('leverage', 1))
                    })

                    logger.info(f"Found active position: {symbol} {side} with amount {position_amount}")

                # 2. Lấy lịch sử giao dịch cho từng symbol
                for symbol in symbols_to_fetch:
                    try:
                        # Lấy thông tin giao dịch gần nhất (tối đa 30 giao dịch)
                        trades = self.binance_client.client.get_account_trades(symbol=symbol, limit=30)
                        logger.info(f"Fetched {len(trades)} recent trades for {symbol}")

                        # 3. Xác định giao dịch cuối cùng cho mỗi vị thế đang mở
                        for position in active_positions.get(symbol, []):
                            # Lọc giao dịch theo chiều của vị thế
                            side = position['side']
                            matching_trades = []

                            for trade in trades:
                                trade_side = trade.get('side', '')
                                if trade_side == side:
                                    matching_trades.append(trade)

                            # Sắp xếp theo thời gian gần nhất
                            matching_trades.sort(key=lambda x: int(x.get('time', 0)), reverse=True)

                            if matching_trades:
                                # Lấy giao dịch gần nhất của vị thế này
                                latest_trade = matching_trades[0]

                                # Lấy orderID thực tế
                                order_id = latest_trade.get('orderId')
                                if not order_id:
                                    order_id = latest_trade.get('id')  # Sử dụng tradeId nếu không có orderId

                                logger.info(f"Found orderID {order_id} for {symbol} {side}")

                                # Tính khối lượng giao dịch theo USDT
                                usdt_amount = abs(position['position_amount']) * position['entry_price']

                                # Tạo thông tin trade với ID thực tế
                                trade_info = {
                                    'id': str(order_id),
                                    'symbol': symbol,
                                    'side': side,
                                    'price': position['entry_price'],
                                    'quantity': round(usdt_amount, 2),  # Số lượng tính theo USDT
                                    'timestamp': datetime.datetime.fromtimestamp(int(latest_trade.get('time', 0))/1000).strftime("%Y-%m-%d %H:%M:%S"),
                                    'status': "OPEN",
                                    'pnl': position['unrealized_pnl'],
                                    'source': "Binance",
                                    'order_type': "Đang mở"
                                }

                                # 4. Tìm SL/TP cho vị thế này
                                try:
                                    open_orders = self.binance_client.client.get_open_orders(symbol=symbol)

                                    # Lọc ra lệnh đang mở theo chiều ngược với vị thế
                                    closing_orders = []
                                    for order in open_orders:
                                        order_side = order.get('side', '')
                                        is_closing_order = (side == "BUY" and order_side == "SELL") or (side == "SELL" and order_side == "BUY")

                                        if is_closing_order:
                                            closing_orders.append(order)

                                    # Tìm SL/TP
                                    for order in closing_orders:
                                        order_type = order.get('type', '')

                                        if order_type == "STOP_MARKET":
                                            sl_price = float(order.get('stopPrice', 0))
                                            # Tính % SL
                                            if side == "BUY":  # Long position
                                                sl_percent = round(((position['entry_price'] - sl_price) / position['entry_price']) * 100, 2)
                                            else:  # Short position
                                                sl_percent = round(((sl_price - position['entry_price']) / position['entry_price']) * 100, 2)

                                            # Lưu cả giá thực và phần trăm
                                            trade_info['stop_loss'] = f"{sl_price} ({sl_percent}%)"

                                        elif order_type == "TAKE_PROFIT_MARKET":
                                            tp_price = float(order.get('stopPrice', 0))
                                            # Tính % TP
                                            if side == "BUY":  # Long position
                                                tp_percent = round(((tp_price - position['entry_price']) / position['entry_price']) * 100, 2)
                                            else:  # Short position
                                                tp_percent = round(((position['entry_price'] - tp_price) / position['entry_price']) * 100, 2)

                                            # Lưu cả giá thực và phần trăm
                                            trade_info['take_profit'] = f"{tp_price} ({tp_percent}%)"

                                except Exception as e:
                                    logger.error(f"Error finding SL/TP for {symbol}: {e}")

                                binance_trades.append(trade_info)
                            else:
                                # Không tìm thấy giao dịch phù hợp - dùng ID từ Binance position nếu có
                                if 'positionIdx' in position:
                                    position_id = f"POS_{position['positionIdx']}_{symbol}"
                                else:
                                    position_id = f"POS_{int(time.time())}_{symbol}_{side}"

                                logger.warning(f"No matching trade found for {symbol} {side}. Using fallback ID: {position_id}")

                                # Tính khối lượng giao dịch theo USDT
                                usdt_amount = abs(position['position_amount']) * position['entry_price']

                                # Tạo thông tin trade với ID backup
                                trade_info = {
                                    'id': position_id,
                                    'symbol': symbol,
                                    'side': side,
                                    'price': position['entry_price'],
                                    'quantity': round(usdt_amount, 2),
                                    'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'status': "OPEN",
                                    'pnl': position['unrealized_pnl'],
                                    'source': "Binance",
                                    'order_type': "Đang mở"
                                }

                                binance_trades.append(trade_info)

                    except Exception as e:
                        logger.error(f"Error fetching trades for {symbol}: {e}")

            except Exception as e:
                logger.error(f"Error getting positions: {e}", exc_info=True)

            # Log tất cả trade để debug
            for trade in binance_trades:
                logger.debug(f"Final trade data: {trade}")

            logger.info(f"Total of {len(binance_trades)} trades fetched from Binance")
            return binance_trades

        except Exception as e:
            logger.error(f"Overall error fetching data from Binance: {e}", exc_info=True)
            return []

    # Đóng vị thế
    def close_position(self, trade_id, symbol, side):
        """Đóng vị thế đang mở"""
        from PyQt5.QtCore import QTimer

        logger.info(f"Closing position: ID={trade_id}, Symbol={symbol}, Side={side}")

        try:
            if not self.binance_client.is_connected():
                self.view.show_message("Lỗi", "Không có kết nối Binance", QMessageBox.Warning)
                return

            # Chiều đóng vị thế ngược với chiều của vị thế
            close_side = "SELL" if side == "BUY" else "BUY"

            # Đóng vị thế
            try:
                # Thay vì sử dụng closePosition=True, chúng ta sẽ lấy vị thế hiện tại và tính toán số lượng chính xác
                positions = self.binance_client.get_positions()

                # Tìm vị thế cần đóng
                position_amount = 0
                for position in positions:
                    if position['symbol'] == symbol:
                        position_amount = float(position.get('positionAmt', 0))
                        break

                if position_amount == 0:
                    self.view.show_message("Lỗi", f"Không tìm thấy vị thế mở cho {symbol}", QMessageBox.Warning)
                    return

                # Khối lượng để đóng (đảo dấu để đóng vị thế)
                quantity = abs(position_amount)

                logger.info(f"Closing position: Symbol={symbol}, Side={close_side}, Quantity={quantity}")

                try:
                    result = self.binance_client.client.new_order(
                        symbol=symbol,
                        side=close_side,
                        type="MARKET",
                        quantity=quantity,
                        reduceOnly=True  # Sử dụng reduceOnly thay vì closePosition
                    )
                except ClientError as e:
                    error_msg = str(e)
                    if "-2015" in error_msg and "Invalid API-key" in error_msg:
                        # Kiểm tra lại kết nối API
                        is_connected, msg = self.binance_client.check_connection()
                        if not is_connected:
                            logging.error(f"Lỗi kết nối API: {msg}")
                            raise Exception(f"Lỗi kết nối API: {msg}")
                        else:
                            logging.error(f"Lỗi quyền hạn API: {error_msg}")
                            raise Exception(f"API key không có quyền đóng vị thế. Hãy kiểm tra cài đặt API key của bạn.")
                    else:
                        raise

                logger.info(f"Close position result: {result}")

                self.view.show_message(
                    "Thành công", 
                    f"Đã đóng vị thế {symbol} ({side}) thành công\n"
                    f"Order ID: {result.get('orderId', 'N/A')}"
                )

                # Vô hiệu hóa nút đóng vị thế
                self.disable_close_button(trade_id)

                # Cập nhật lại danh sách giao dịch
                self.view.statusbar.showMessage("Đang cập nhật danh sách giao dịch...", 2000)

                # Cập nhật ngay lập tức
                QTimer.singleShot(2000, self.force_refresh_trades)

            except Exception as e:
                error_msg = f"Lỗi khi đóng vị thế: {e}"
                logger.error(error_msg, exc_info=True)
                self.view.show_message("Lỗi", error_msg, QMessageBox.Warning)

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
            # Tìm đối tượng MainController
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
        # Tham chiếu đến MainController và gọi load_trades
        # Phương pháp này phụ thuộc vào cấu trúc của ứng dụng
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