import time
import datetime
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from config.logging_config import setup_logger
from binance.error import ClientError
from models import binance_data_singleton

# Tạo logger cho module này
logger = setup_logger(__name__)

class AutoTrader(QThread):
    trade_update = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    close_position_signal = pyqtSignal(str, str, str)  # trade_id, symbol, side

    def __init__(self, binance_client, symbol, timeframe, amount, leverage, stop_loss, trading_method="Đường Base Line"):
        super().__init__()
        self.binance_client = binance_client
        self.symbol = symbol
        self.timeframe = timeframe
        self.amount = amount
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.trading_method = trading_method
        self.running = True
        self.current_position = None  # Theo dõi vị thế hiện tại: None hoặc {"side": "BUY"/"SELL", "trade_id": "id"}
        self.current_baseline = None  # Lưu giá trị baseline hiện tại
        
        # Lấy tham chiếu đến data model
        self.data_model = binance_data_singleton.get_instance()

    def run(self):
        while self.running:
            try:
                self.status_update.emit(f"Đang phân tích thị trường với phương pháp {self.trading_method}...")

                # Kiểm tra vị thế hiện tại trước
                self.check_current_position()

                # Lấy dữ liệu lịch sử giá với Futures Connector
                klines_response = self.data_model.get_klines(
                    symbol=self.symbol,
                    interval=self.timeframe,
                    limit=200  # Tăng số lượng nến để có đủ dữ liệu cho Ichimoku và Baseline
                )

                # Phân tích dựa trên phương pháp được chọn
                if self.trading_method == "Đường Base Line":
                    signal, close_signal = self.analyze_with_baseline(klines_response)
                elif self.trading_method == "Mây Ichimoku":
                    signal, close_signal = self.analyze_with_ichimoku(klines_response)
                else:
                    # Phương pháp mặc định nếu không xác định
                    signal, close_signal = self.analyze_with_baseline(klines_response)

                current_price = float(klines_response[-1][4])  # Giá đóng cửa của nến cuối cùng

                # Xử lý tín hiệu đóng vị thế nếu có
                if close_signal and self.current_position:
                    self.status_update.emit(f"Phát hiện tín hiệu ĐÓNG VỊ THẾ từ {self.trading_method}...")
                    self.close_current_position(current_price)
                    continue  # Sau khi đóng vị thế, tiếp tục vòng lặp để cập nhật trạng thái

                # Xử lý tín hiệu mở vị thế mới nếu không có vị thế hiện tại
                if signal and not self.current_position:
                    if signal == "BUY":
                        self.status_update.emit(f"Phát hiện tín hiệu MUA từ {self.trading_method}...")
                        self.execute_trade("BUY", current_price)
                    elif signal == "SELL":
                        self.status_update.emit(f"Phát hiện tín hiệu BÁN từ {self.trading_method}...")
                        self.execute_trade("SELL", current_price)
                else:
                    # Không có tín hiệu hoặc đã có vị thế
                    if self.current_position:
                        self.status_update.emit(f"Đang theo dõi vị thế {self.current_position['side']} hiện tại...")
                    else:
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

            self.status_update.emit(f"Đang giao dịch ở khung {self.timeframe} với {self.trading_method}\nNghỉ {time_sleep} giây trước lần kiểm tra tiếp theo...")
            
            # Nghỉ theo từng bước nhỏ 0.5 giây để có thể thoát sớm
            sleep_count = 0
            while self.running and sleep_count < time_sleep * 2:
                time.sleep(0.5)
                sleep_count += 1

    def check_current_position(self):
        """Kiểm tra xem có vị thế đang mở hay không"""
        try:
            positions = self.data_model.get_positions()
            
            # Tìm vị thế cho symbol hiện tại
            current_pos = None
            for position in positions:
                if position['symbol'] == self.symbol:
                    pos_amount = float(position.get('positionAmt', 0))
                    if pos_amount != 0:  # Có vị thế đang mở
                        side = "BUY" if pos_amount > 0 else "SELL"
                        pos_id = position.get('id', f"POS_{self.symbol}_{side}")
                        
                        # Lưu thông tin vị thế
                        current_pos = {
                            "side": side,
                            "trade_id": pos_id,
                            "quantity": abs(pos_amount),
                            "entry_price": float(position.get('entryPrice', 0)),
                            "entry_baseline": self.current_position.get("entry_baseline") if self.current_position else None
                        }
                        break
            
            # Cập nhật trạng thái vị thế
            self.current_position = current_pos
            
            if current_pos:
                self.status_update.emit(f"Phát hiện vị thế đang mở: {current_pos['side']} {self.symbol}")
            else:
                self.status_update.emit("Không có vị thế đang mở")
                
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra vị thế: {e}")
            self.status_update.emit(f"Lỗi khi kiểm tra vị thế: {e}")

    def close_current_position(self, current_price):
        """Đóng vị thế hiện tại"""
        if not self.current_position:
            self.status_update.emit("Không có vị thế nào để đóng")
            return
        
        try:
            trade_id = self.current_position['trade_id']
            side = self.current_position['side']
            
            # Phát tín hiệu đóng vị thế
            self.status_update.emit(f"Đang đóng vị thế {side} {self.symbol}...")
            self.close_position_signal.emit(str(trade_id), self.symbol, side)
            
            # Đặt current_position về None
            self.current_position = None
            
            # Đợi một khoảng thời gian để vị thế được đóng
            time.sleep(2)
            
        except Exception as e:
            error_msg = f"Lỗi khi đóng vị thế: {e}"
            self.status_update.emit(error_msg)
            logger.error(error_msg)

    # [Các phương thức phân tích giữ nguyên]

    def execute_trade(self, side, current_price):
        try:
            # Tính toán số lượng
            quantity = self.data_model.calculate_order_quantity(self.symbol, self.amount)

            if not quantity:
                self.status_update.emit("Không thể tính toán số lượng lệnh")
                return

            self.status_update.emit(f"Đặt lệnh {side} với số lượng {quantity}, đòn bẩy {self.leverage}x...")

            # Đặt lệnh
            success, result = self.data_model.place_order(
                self.symbol, side, quantity, self.leverage, self.stop_loss, 0
            )

            if success:
                trade_info = result
                # Thêm thông tin phương pháp giao dịch và đòn bẩy vào thông tin giao dịch
                trade_info['source'] = f"Auto ({self.trading_method})"
                
                # Đảm bảo đòn bẩy được cập nhật chính xác
                if 'leverage' not in trade_info or not trade_info['leverage']:
                    trade_info['leverage'] = self.leverage
                
                # Lưu thông tin baseline hiện tại vào thông tin giao dịch
                if hasattr(self, 'current_baseline'):
                    trade_info['entry_baseline'] = self.current_baseline
                    
                # Log đòn bẩy và baseline để debug
                logger.info(f"Trade executed with leverage: {trade_info.get('leverage', 'Not set')}, " +
                        f"baseline: {getattr(self, 'current_baseline', 'Not calculated')}")
                
                # Sử dụng thời gian từ kết quả đã được chuyển đổi sang múi giờ +7
                order_time = trade_info.get('timestamp', '')
                
                self.status_update.emit(f"Đã đặt lệnh {side} thành công!")
                
                # Lưu thông tin vị thế hiện tại
                self.current_position = {
                    "side": side,
                    "trade_id": trade_info.get('id', f"POS_{self.symbol}_{side}"),
                    "quantity": quantity,
                    "entry_price": current_price,
                    "leverage": trade_info.get('leverage', self.leverage),
                    "entry_baseline": getattr(self, 'current_baseline', None),  # Lưu giá trị baseline khi vào lệnh
                    "timestamp": order_time
                }
                
                # Gửi tín hiệu cập nhật giao dịch
                self.trade_update.emit(trade_info)
            else:
                self.status_update.emit(f"Lỗi đặt lệnh: {result}")

        except Exception as e:
            error_msg = f"Lỗi đặt lệnh (Hệ thống): {e}"
            self.status_update.emit(error_msg)
            logger.error(error_msg)

    # [Giữ nguyên các phương thức phân tích khác - calculate_jma, calculate_rsi, v.v.]

    def stop(self):
        logger.info("Stopping AutoTrader thread")
        self.running = False