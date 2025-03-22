import time
import datetime
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from config.logging_config import setup_logger
from binance.error import ClientError

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

    def run(self):
        while self.running:
            try:
                self.status_update.emit(f"Đang phân tích thị trường với phương pháp {self.trading_method}...")

                # Kiểm tra vị thế hiện tại trước
                self.check_current_position()

                # Lấy dữ liệu lịch sử giá với Futures Connector
                klines_response = self.binance_client.client.klines(
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
            positions = self.binance_client.get_positions()
            
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

    def analyze_with_baseline(self, klines_response):
        """
        Phương pháp phân tích sử dụng Baseline JMA theo chiến lược cụ thể:
        - JMA với tham số 75, 5, 2 cho baseline
        - JMA với tham số 150, 0, 2 cho baseline_slow
        - Điều kiện RSI và tỉ lệ phần trăm
        """
        try:
            # Chuyển đổi dữ liệu thành mảng numpy để xử lý hiệu quả
            opens = np.array([float(k[1]) for k in klines_response])
            highs = np.array([float(k[2]) for k in klines_response])
            lows = np.array([float(k[3]) for k in klines_response])
            close_prices = np.array([float(k[4]) for k in klines_response])
            volumes = np.array([float(k[5]) for k in klines_response])
            
            # Lấy giá hiện tại
            current_price = close_prices[-1]
            prev_close = close_prices[-2]
            
            # Tính body của nến hiện tại
            current_body = abs(opens[-1] - close_prices[-1])
            current_is_green = close_prices[-1] > opens[-1]
            
            # Tính JMA (Jurik Moving Average) cho baseline và baseline_slow
            baseline = self.calculate_jma(close_prices, 75, 5, 2)
            baseline_slow = self.calculate_jma(close_prices, 150, 0, 2)
            
            # Tính RSI
            rsi = self.calculate_rsi(close_prices, 14)
            
            # Tính các điều kiện X, Y
            X = abs(baseline[-1] - baseline_slow[-1]) / current_price * 100
            Y = abs(current_price - baseline[-1]) / current_price * 100
            baseline_slow_change = abs(baseline_slow[-1] - baseline_slow[-6]) / current_price * 100
            
            # Kiểm tra điều kiện tăng/giảm liên tục của baseline
            baseline_increasing = all(baseline[-6+i] < baseline[-6+i+1] for i in range(5))
            baseline_decreasing = all(baseline[-6+i] > baseline[-6+i+1] for i in range(5))
            
            # Log thông tin để debug
            self.status_update.emit(
                f"Baseline JMA - RSI: {rsi[-1]:.2f}, X: {X:.2f}%, Y: {Y:.2f}%, "
                f"Baseline trend: {'Up' if baseline_increasing else ('Down' if baseline_decreasing else 'Sideway')}, "
                f"Slow change: {baseline_slow_change:.2f}%"
            )
            
            # Tín hiệu mua/bán (mở vị thế)
            open_signal = None
            
            # Điều kiện vào lệnh LONG
            if (X < 1.0 and 
                Y < 0.5 and 
                rsi[-1] < 55 and 
                baseline_increasing and 
                baseline_slow_change > 0.15 and 
                prev_close > baseline[-2]):
                
                # Kiểm tra thêm điều kiện về thân nến nếu là nến xanh
                if not current_is_green or (current_is_green and (close_prices[-2] - baseline[-2]) > current_body * 2/3):
                    open_signal = "BUY"
                    self.status_update.emit(f"Tín hiệu MUA từ Baseline JMA - RSI: {rsi[-1]:.2f}, X: {X:.2f}%, Y: {Y:.2f}%")
            
            # Điều kiện vào lệnh SHORT
            elif (X < 1.0 and 
                Y < 0.5 and 
                rsi[-1] < 55 and 
                baseline_decreasing and 
                baseline_slow_change > 0.15 and 
                prev_close < baseline[-2]):
                
                # Kiểm tra thêm điều kiện về thân nến nếu là nến đỏ
                if current_is_green or (not current_is_green and (baseline[-2] - close_prices[-2]) > current_body * 2/3):
                    open_signal = "SELL"
                    self.status_update.emit(f"Tín hiệu BÁN từ Baseline JMA - RSI: {rsi[-1]:.2f}, X: {X:.2f}%, Y: {Y:.2f}%")
            
            # Tín hiệu đóng vị thế
            close_signal = False
            entry_baseline = None
            
            # Nếu có vị thế, kiểm tra điều kiện đóng vị thế
            if self.current_position:
                # Lấy giá trị baseline lúc vào lệnh (nếu đã lưu)
                entry_baseline = self.current_position.get('entry_baseline')
                
                if self.current_position['side'] == "BUY":
                    # Điều kiện đóng vị thế LONG
                    if prev_close < baseline[-2] or (entry_baseline and current_price < entry_baseline):
                        close_signal = True
                        self.status_update.emit(f"Tín hiệu ĐÓNG vị thế LONG - Prev close: {prev_close:.2f}, Baseline: {baseline[-2]:.2f}")
                
                elif self.current_position['side'] == "SELL":
                    # Điều kiện đóng vị thế SHORT
                    if prev_close > baseline[-2] or (entry_baseline and current_price > entry_baseline):
                        close_signal = True
                        self.status_update.emit(f"Tín hiệu ĐÓNG vị thế SHORT - Prev close: {prev_close:.2f}, Baseline: {baseline[-2]:.2f}")
            
            # Lưu giá trị baseline hiện tại để sử dụng khi mở vị thế mới
            self.current_baseline = baseline[-1]
            
            return open_signal, close_signal
        except Exception as e:
            self.status_update.emit(f"Lỗi khi phân tích Baseline: {e}")
            logger.error(f"Error in baseline analysis: {e}", exc_info=True)
            return None, False

    def analyze_with_ichimoku(self, klines_response):
        """Phương pháp phân tích sử dụng mây Ichimoku"""
        # Phân tích kỹ thuật phức tạp hơn với mây Ichimoku
        # Lấy giá cao, thấp, đóng cửa
        highs = [float(k[2]) for k in klines_response]
        lows = [float(k[3]) for k in klines_response]
        close_prices = [float(k[4]) for k in klines_response]
        
        # Tính toán các thành phần của Ichimoku
        tenkan_sen_period = 9
        kijun_sen_period = 26
        senkou_span_b_period = 52
        
        # Tenkan-sen (Conversion Line): (highest high + lowest low) / 2 for the past 9 periods
        tenkan_sen = 0
        if len(highs) >= tenkan_sen_period:
            tenkan_sen = (max(highs[-tenkan_sen_period:]) + min(lows[-tenkan_sen_period:])) / 2
        
        # Kijun-sen (Base Line): (highest high + lowest low) / 2 for the past 26 periods
        kijun_sen = 0
        if len(highs) >= kijun_sen_period:
            kijun_sen = (max(highs[-kijun_sen_period:]) + min(lows[-kijun_sen_period:])) / 2
        
        # Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen) / 2 (plotted 26 periods ahead)
        senkou_span_a = (tenkan_sen + kijun_sen) / 2
        
        # Senkou Span B (Leading Span B): (highest high + lowest low) / 2 for the past 52 periods (plotted 26 periods ahead)
        senkou_span_b = 0
        if len(highs) >= senkou_span_b_period:
            senkou_span_b = (max(highs[-senkou_span_b_period:]) + min(lows[-senkou_span_b_period:])) / 2
        
        current_price = close_prices[-1]
        prev_price = close_prices[-2]
        
        # Cập nhật trạng thái
        self.status_update.emit(
            f"Phương pháp Ichimoku - Tenkan: {tenkan_sen:.2f}, Kijun: {kijun_sen:.2f}, "
            f"Span A: {senkou_span_a:.2f}, Span B: {senkou_span_b:.2f}"
        )
        
        # Tín hiệu mở vị thế
        open_signal = None
        
        # Tín hiệu mua: 
        # 1. Giá đóng cửa vượt trên mây (trên cả Span A và Span B)
        # 2. Tenkan-sen vượt trên Kijun-sen (Cross up)
        if (current_price > senkou_span_a and current_price > senkou_span_b and 
            tenkan_sen > kijun_sen and close_prices[-2] <= kijun_sen):
            open_signal = "BUY"
        
        # Tín hiệu bán:
        # 1. Giá đóng cửa vượt dưới mây (dưới cả Span A và Span B)
        # 2. Tenkan-sen vượt dưới Kijun-sen (Cross down)
        elif (current_price < senkou_span_a and current_price < senkou_span_b and 
            tenkan_sen < kijun_sen and close_prices[-2] >= kijun_sen):
            open_signal = "SELL"
            
        # Tín hiệu đóng vị thế
        close_signal = False
        
        # Đóng vị thế BUY khi:
        # 1. Giá cắt xuống dưới Kijun-sen (đường cơ sở)
        # 2. Tenkan-sen cắt xuống dưới Kijun-sen
        if self.current_position and self.current_position['side'] == "BUY":
            if (current_price < kijun_sen and prev_price >= kijun_sen) or \
            (tenkan_sen < kijun_sen and tenkan_sen > kijun_sen):
                close_signal = True
                
        # Đóng vị thế SELL khi:
        # 1. Giá cắt lên trên Kijun-sen (đường cơ sở)
        # 2. Tenkan-sen cắt lên trên Kijun-sen
        elif self.current_position and self.current_position['side'] == "SELL":
            if (current_price > kijun_sen and prev_price <= kijun_sen) or \
            (tenkan_sen > kijun_sen and tenkan_sen < kijun_sen):
                close_signal = True
        
        # Điều kiện đóng vị thế bổ sung: Đạt mục tiêu lợi nhuận hoặc cắt lỗ
        if self.current_position:
            entry_price = self.current_position['entry_price']
            profit_percent = 0
            
            if self.current_position['side'] == "BUY":
                profit_percent = (current_price - entry_price) / entry_price * 100
            else:  # SELL
                profit_percent = (entry_price - current_price) / entry_price * 100
                
            # Đóng vị thế nếu lợi nhuận > 3% hoặc lỗ > 2%
            if profit_percent >= 3 or profit_percent <= -2:
                close_signal = True
                self.status_update.emit(f"Tín hiệu đóng vị thế theo P/L: {profit_percent:.2f}%")
                
        return open_signal, close_signal

    def execute_trade(self, side, current_price):
        try:
            # Tính toán số lượng
            quantity = self.binance_client.calculate_order_quantity(self.symbol, self.amount)

            if not quantity:
                self.status_update.emit("Không thể tính toán số lượng lệnh")
                return

            self.status_update.emit(f"Đặt lệnh {side} với số lượng {quantity}, đòn bẩy {self.leverage}x...")

            # Đặt lệnh
            success, result = self.binance_client.place_order(
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

    def calculate_jma(self, data, length=75, phase=5, power=2):
        """
        Tính toán Jurik Moving Average (JMA)
        
        Tham số:
        - data: Mảng giá (thường là giá đóng cửa)
        - length: Độ dài của trung bình động
        - phase: Tham số pha (-100 đến 100)
        - power: Tham số mũ (thường là 2)
        
        Trả về:
        - Mảng giá trị JMA
        """
        try:
            # Sử dụng phương pháp xấp xỉ cho JMA
            # JMA là thuật toán phức tạp, dưới đây là một xấp xỉ đơn giản
            phase_ratio = 0.5 if phase == 0 else (phase / 100 + 0.5)
            beta = 0.45 * (length - 1) / (0.45 * (length - 1) + 2)
            alpha = pow(beta, power)
            
            # Tính EMA với hệ số alpha
            jma = np.zeros_like(data)
            jma[0] = data[0]
            
            for i in range(1, len(data)):
                jma[i] = alpha * data[i] + (1 - alpha) * jma[i-1]
            
            # Điều chỉnh theo phase
            if phase_ratio != 0.5:
                jma = phase_ratio * jma + (1 - phase_ratio) * data
            
            return jma
        except Exception as e:
            logger.error(f"Error calculating JMA: {e}")
            # Fallback to simple moving average
            n = min(length, len(data))
            return np.convolve(data, np.ones(n)/n, mode='valid')

    def calculate_rsi(self, prices, window=14):
        """
        Tính RSI (Relative Strength Index)
        
        Tham số:
        - prices: Mảng giá đóng cửa
        - window: Cửa sổ tính RSI (thường là 14)
        
        Trả về:
        - Mảng giá trị RSI
        """
        try:
            # Tính các thay đổi giá
            deltas = np.diff(prices)
            # Tạo mảng có cùng kích thước với giá ban đầu
            rsi = np.zeros_like(prices)
            rsi[0] = 50  # Giá trị mặc định cho phần tử đầu tiên
            
            # Tách thành gain và loss
            gains = deltas.copy()
            losses = deltas.copy()
            gains[gains < 0] = 0
            losses[losses > 0] = 0
            losses = abs(losses)
            
            # Tính average gain và average loss
            avg_gain = np.zeros_like(prices)
            avg_loss = np.zeros_like(prices)
            
            # Tính giá trị ban đầu
            if len(gains) >= window:
                avg_gain[window] = np.mean(gains[:window])
                avg_loss[window] = np.mean(losses[:window])
                
                # Tính giá trị tiếp theo
                for i in range(window+1, len(prices)):
                    avg_gain[i] = (avg_gain[i-1] * (window-1) + gains[i-1]) / window
                    avg_loss[i] = (avg_loss[i-1] * (window-1) + losses[i-1]) / window
                
                # Tính RSI
                rs = avg_gain / np.where(avg_loss == 0, 0.001, avg_loss)  # Tránh chia cho 0
                rsi = 100 - (100 / (1 + rs))
            
            return rsi
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return np.full_like(prices, 50)  # Trả về 50 nếu có lỗi

    def stop(self):
        logger.info("Stopping AutoTrader thread")
        self.running = False